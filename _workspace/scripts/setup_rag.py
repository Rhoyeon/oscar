"""Oscar RAG setup script.

Builds a hybrid (BM25 + vector) retrieval system over the knowledge graph
produced by the Oscar pipeline. Uses adapter pattern so the embedding model
and the vector store can be swapped independently.

Layers:
  1) Loaders             - load ontology + knowledge graph JSON files.
  2) Text builders       - render nodes/edges/subgraphs into embedding strings.
  3) Embedding adapter   - openai / sentence-transformers / hash-stub.
  4) Vector store        - chroma (default) / in-memory fallback.
  5) BM25 index          - rank_bm25 (fallback to simple TF scoring).
  6) Hybrid retriever    - vector + BM25 fusion with ontology context expansion.
  7) Query interface     - oscar_query(text, top_k).

Run:
  python setup_rag.py
"""

from __future__ import annotations

import json
import math
import os
import re
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]            # _workspace/
CONFIG_PATH = ROOT / "04_rag_config.json"
SCHEMA_PATH = ROOT / "02_ontology_schema.json"
GRAPH_PATH = ROOT / "03_knowledge_graph.json"
PERSIST_DIR = ROOT / "chroma_db"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Embedding adapters
# ---------------------------------------------------------------------------


class EmbeddingAdapter:
    """Pluggable embedding backend."""

    name = "base"
    dimensions = 0

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError


class SentenceTransformersAdapter(EmbeddingAdapter):
    name = "sentence-transformers"

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        from sentence_transformers import SentenceTransformer  # lazy
        self._model = SentenceTransformer(model_name)
        self.dimensions = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        return [v.tolist() for v in self._model.encode(list(texts), show_progress_bar=False)]


class OpenAIAdapter(EmbeddingAdapter):
    name = "openai"

    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI  # lazy
        self._client = OpenAI()
        self._model = model
        self.dimensions = 1536

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(model=self._model, input=list(texts))
        return [d.embedding for d in resp.data]


class HashStubAdapter(EmbeddingAdapter):
    """Deterministic offline fallback - hashes tokens into a fixed-dim vector.

    Not semantically meaningful but lets the pipeline run end-to-end without
    network access or model downloads.
    """

    name = "stub-hash"

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for token in _tokenize(text):
                h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
                vec[h % self.dimensions] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def build_embedding_adapter(preferred: str = "sentence-transformers") -> EmbeddingAdapter:
    order = [preferred, "sentence-transformers", "openai", "stub-hash"]
    seen = set()
    for choice in order:
        if choice in seen:
            continue
        seen.add(choice)
        try:
            if choice == "sentence-transformers":
                return SentenceTransformersAdapter()
            if choice == "openai" and os.environ.get("OPENAI_API_KEY"):
                return OpenAIAdapter()
            if choice == "stub-hash":
                return HashStubAdapter()
        except Exception as exc:  # pragma: no cover
            print(f"[embedding] {choice} unavailable: {exc}")
    return HashStubAdapter()


# ---------------------------------------------------------------------------
# Vector store adapters
# ---------------------------------------------------------------------------


@dataclass
class SearchHit:
    id: str
    score: float
    document: str
    metadata: Dict[str, Any]


class VectorStore:
    def upsert(self, collection: str, ids: List[str], embeddings: List[List[float]],
               documents: List[str], metadatas: List[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def query(self, collection: str, embedding: List[float], top_k: int) -> List[SearchHit]:
        raise NotImplementedError


class ChromaStore(VectorStore):
    def __init__(self, persist_directory: Path):
        import chromadb  # lazy
        persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_directory))
        self._collections: Dict[str, Any] = {}

    def _coll(self, name: str):
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(name=name)
        return self._collections[name]

    def upsert(self, collection, ids, embeddings, documents, metadatas):
        self._coll(collection).upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas,
        )

    def query(self, collection, embedding, top_k):
        res = self._coll(collection).query(query_embeddings=[embedding], n_results=top_k)
        hits = []
        for i, _id in enumerate(res["ids"][0]):
            hits.append(SearchHit(
                id=_id,
                score=1.0 - float(res["distances"][0][i]),
                document=res["documents"][0][i],
                metadata=res["metadatas"][0][i] or {},
            ))
        return hits


class InMemoryStore(VectorStore):
    """Cosine-similarity in-memory vector store fallback."""

    def __init__(self):
        self._data: Dict[str, List[Tuple[str, List[float], str, Dict[str, Any]]]] = defaultdict(list)

    def upsert(self, collection, ids, embeddings, documents, metadatas):
        existing = {row[0]: i for i, row in enumerate(self._data[collection])}
        for _id, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
            row = (_id, emb, doc, meta)
            if _id in existing:
                self._data[collection][existing[_id]] = row
            else:
                self._data[collection].append(row)

    def query(self, collection, embedding, top_k):
        def cos(a, b):
            num = sum(x * y for x, y in zip(a, b))
            da = math.sqrt(sum(x * x for x in a)) or 1.0
            db = math.sqrt(sum(y * y for y in b)) or 1.0
            return num / (da * db)

        scored = [
            SearchHit(_id, cos(embedding, emb), doc, meta)
            for _id, emb, doc, meta in self._data[collection]
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]


def build_vector_store(preferred: str = "chroma") -> VectorStore:
    if preferred == "chroma":
        try:
            return ChromaStore(PERSIST_DIR)
        except Exception as exc:
            print(f"[vector_store] chroma unavailable: {exc} — falling back to in-memory")
    return InMemoryStore()


# ---------------------------------------------------------------------------
# Tokenizer + BM25
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


class BM25Index:
    """Minimal BM25 implementation (Okapi)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[List[str]] = []
        self.ids: List[str] = []
        self.documents: List[str] = []
        self.metadatas: List[Dict[str, Any]] = []
        self.df: Counter = Counter()
        self.avgdl: float = 0.0
        self.idf: Dict[str, float] = {}

    def add(self, _id: str, document: str, metadata: Dict[str, Any]) -> None:
        toks = _tokenize(document)
        self.ids.append(_id)
        self.docs.append(toks)
        self.documents.append(document)
        self.metadatas.append(metadata)
        for t in set(toks):
            self.df[t] += 1

    def finalize(self) -> None:
        n = len(self.docs)
        self.avgdl = (sum(len(d) for d in self.docs) / n) if n else 0.0
        self.idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for term, df in self.df.items()
        }

    def search(self, query: str, top_k: int) -> List[SearchHit]:
        q_toks = _tokenize(query)
        if not q_toks or not self.docs:
            return []
        scores = []
        for i, doc in enumerate(self.docs):
            tf = Counter(doc)
            dl = len(doc) or 1
            score = 0.0
            for term in q_toks:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                f = tf[term]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                score += idf * (f * (self.k1 + 1)) / denom
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [
            SearchHit(self.ids[i], s, self.documents[i], self.metadatas[i])
            for i, s in scores[:top_k]
        ]


# ---------------------------------------------------------------------------
# Text builders for nodes / edges / subgraphs
# ---------------------------------------------------------------------------


def _props_str(props: Dict[str, Any]) -> str:
    if not props:
        return ""
    parts = []
    for k, v in props.items():
        if v is None or k == "entity_type_raw":
            continue
        parts.append(f"{k}={v}")
    return "; ".join(parts)


def node_text(node: dict) -> str:
    return (
        f"{node['class_label']}: {node['label']}. "
        f"{_props_str(node.get('properties', {}))}"
    ).strip()


def edge_text(edge: dict, node_by_id: Dict[str, dict]) -> str:
    src = node_by_id[edge["source"]]
    tgt = node_by_id[edge["target"]]
    return (
        f"{src['label']} ({src['class_label']}) "
        f"--{edge['relation_label']}--> "
        f"{tgt['label']} ({tgt['class_label']})"
    )


def subgraph_text(node: dict, neighbors: List[Tuple[dict, dict, str]]) -> str:
    """neighbors: list of (edge, neighbor_node, direction) where direction in {out, in}."""
    head = f"[{node['class_label']}] {node['label']} :: {node.get('properties', {}).get('description', '')}"
    lines = [head]
    for edge, nbr, direction in neighbors:
        arrow = "->" if direction == "out" else "<-"
        lines.append(
            f"  {arrow} {edge['relation_label']} {arrow} "
            f"{nbr['label']} [{nbr['class_label']}]"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ontology helper
# ---------------------------------------------------------------------------


class Ontology:
    def __init__(self, schema: dict):
        self.schema = schema
        self.classes = {c["id"]: c for c in schema["classes"]}
        self.properties = {p["id"]: p for p in schema["properties"]}

    def ancestors(self, class_id: str) -> List[str]:
        out = []
        cur = self.classes.get(class_id)
        while cur and cur.get("parent"):
            out.append(cur["parent"])
            cur = self.classes.get(cur["parent"])
        return out

    def class_label(self, class_id: str) -> str:
        c = self.classes.get(class_id)
        return c["name"] if c else class_id


# ---------------------------------------------------------------------------
# Knowledge graph wrapper
# ---------------------------------------------------------------------------


class KnowledgeGraph:
    def __init__(self, kg: dict):
        self.kg = kg
        self.nodes: List[dict] = kg["nodes"]
        self.edges: List[dict] = kg["edges"]
        self.node_by_id: Dict[str, dict] = {n["id"]: n for n in self.nodes}
        self.out_edges: Dict[str, List[dict]] = defaultdict(list)
        self.in_edges: Dict[str, List[dict]] = defaultdict(list)
        for e in self.edges:
            self.out_edges[e["source"]].append(e)
            self.in_edges[e["target"]].append(e)

    def neighbors(self, node_id: str, hops: int = 1) -> List[Tuple[dict, dict, str]]:
        """Return [(edge, neighbor_node, direction), ...] within `hops`."""
        seen_nodes = {node_id}
        frontier = [node_id]
        results: List[Tuple[dict, dict, str]] = []
        for _ in range(hops):
            next_frontier = []
            for nid in frontier:
                for e in self.out_edges.get(nid, []):
                    if e["target"] not in seen_nodes:
                        results.append((e, self.node_by_id[e["target"]], "out"))
                        seen_nodes.add(e["target"])
                        next_frontier.append(e["target"])
                for e in self.in_edges.get(nid, []):
                    if e["source"] not in seen_nodes:
                        results.append((e, self.node_by_id[e["source"]], "in"))
                        seen_nodes.add(e["source"])
                        next_frontier.append(e["source"])
            frontier = next_frontier
        return results


# ---------------------------------------------------------------------------
# Index orchestration
# ---------------------------------------------------------------------------


@dataclass
class OscarRAG:
    config: dict
    ontology: Ontology
    graph: KnowledgeGraph
    embedder: EmbeddingAdapter
    store: VectorStore
    bm25: Dict[str, BM25Index] = field(default_factory=dict)

    # ------------------------------------------------------------------ build
    def build(self) -> None:
        self._index_nodes()
        self._index_edges()
        self._index_subgraphs()

    def _index_nodes(self) -> None:
        ids, docs, metas = [], [], []
        for n in self.graph.nodes:
            ids.append(n["id"])
            docs.append(node_text(n))
            metas.append({
                "kind": "node",
                "class": n["class"],
                "class_label": n["class_label"],
                "label": n["label"],
                "uri": n["uri"],
            })
        self._index("nodes", ids, docs, metas)

    def _index_edges(self) -> None:
        ids, docs, metas = [], [], []
        for e in self.graph.edges:
            ids.append(e["id"])
            docs.append(edge_text(e, self.graph.node_by_id))
            metas.append({
                "kind": "edge",
                "relation": e["relation"],
                "relation_label": e["relation_label"],
                "source": e["source"],
                "target": e["target"],
            })
        self._index("edges", ids, docs, metas)

    def _index_subgraphs(self) -> None:
        ids, docs, metas = [], [], []
        for n in self.graph.nodes:
            nbrs = self.graph.neighbors(n["id"], hops=2)
            ids.append(f"sub_{n['id']}")
            docs.append(subgraph_text(n, nbrs))
            metas.append({
                "kind": "subgraph",
                "center": n["id"],
                "center_label": n["label"],
                "class": n["class"],
                "neighbor_count": len(nbrs),
            })
        self._index("subgraphs", ids, docs, metas)

    def _index(self, collection: str, ids: List[str], docs: List[str],
               metas: List[Dict[str, Any]]) -> None:
        embeddings = self.embedder.embed(docs)
        self.store.upsert(collection, ids, embeddings, docs, metas)
        bm = BM25Index()
        for _id, doc, meta in zip(ids, docs, metas):
            bm.add(_id, doc, meta)
        bm.finalize()
        self.bm25[collection] = bm
        print(f"[index] {collection}: {len(ids)} items "
              f"(embedder={self.embedder.name}, dim={self.embedder.dimensions})")

    # ----------------------------------------------------------------- search
    def hybrid_search(self, query: str, collection: str, top_k: int = 10,
                      bm25_candidates: int = 50) -> List[SearchHit]:
        q_emb = self.embedder.embed([query])[0]
        vec_hits = self.store.query(collection, q_emb, top_k=bm25_candidates)
        bm25_hits = self.bm25[collection].search(query, top_k=bm25_candidates)

        # Reciprocal Rank Fusion
        k = 60
        scores: Dict[str, float] = defaultdict(float)
        meta: Dict[str, SearchHit] = {}
        for rank, h in enumerate(vec_hits):
            scores[h.id] += 1.0 / (k + rank + 1)
            meta[h.id] = h
        for rank, h in enumerate(bm25_hits):
            scores[h.id] += 1.0 / (k + rank + 1)
            meta.setdefault(h.id, h)
        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [SearchHit(_id, s, meta[_id].document, meta[_id].metadata) for _id, s in fused]

    # --------------------------------------------------------- context expand
    def expand_context(self, hits: List[SearchHit], hops: int = 1) -> List[dict]:
        """Pull ontology-aware context (class hierarchy + KG neighborhood)."""
        out = []
        for h in hits:
            entry: Dict[str, Any] = {"hit": h.__dict__}
            if h.metadata.get("kind") == "node":
                node = self.graph.node_by_id.get(h.id)
                if node:
                    entry["class_path"] = [
                        self.ontology.class_label(c)
                        for c in [node["class"], *self.ontology.ancestors(node["class"])]
                    ]
                    entry["neighbors"] = [
                        {
                            "relation": e["relation_label"],
                            "direction": d,
                            "neighbor": nbr["label"],
                            "neighbor_class": nbr["class_label"],
                        }
                        for e, nbr, d in self.graph.neighbors(h.id, hops=hops)
                    ]
            elif h.metadata.get("kind") == "edge":
                src = self.graph.node_by_id.get(h.metadata["source"])
                tgt = self.graph.node_by_id.get(h.metadata["target"])
                entry["endpoints"] = {
                    "source": {"label": src["label"], "class": src["class_label"]} if src else None,
                    "target": {"label": tgt["label"], "class": tgt["class_label"]} if tgt else None,
                }
            elif h.metadata.get("kind") == "subgraph":
                center = self.graph.node_by_id.get(h.metadata["center"])
                if center:
                    entry["center_class_path"] = [
                        self.ontology.class_label(c)
                        for c in [center["class"], *self.ontology.ancestors(center["class"])]
                    ]
            out.append(entry)
        return out

    # ----------------------------------------------------------------- query
    def query(self, text: str, top_k: int = 10) -> dict:
        retrieval_cfg = self.config.get("retrieval", {})
        bm25_candidates = retrieval_cfg.get("bm25_candidates", 50)
        hops = retrieval_cfg.get("context_expansion_hops", 1)

        results: Dict[str, List[dict]] = {}
        for collection in self.config["vector_store"]["collections"]:
            hits = self.hybrid_search(text, collection, top_k=top_k,
                                       bm25_candidates=bm25_candidates)
            results[collection] = self.expand_context(hits, hops=hops) \
                if retrieval_cfg.get("context_expansion", True) else \
                [{"hit": h.__dict__} for h in hits]
        return {"query": text, "top_k": top_k, "results": results}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


_RAG_SINGLETON: Optional[OscarRAG] = None


def get_rag() -> OscarRAG:
    global _RAG_SINGLETON
    if _RAG_SINGLETON is not None:
        return _RAG_SINGLETON

    config = load_json(CONFIG_PATH)
    schema = load_json(SCHEMA_PATH)
    graph = load_json(GRAPH_PATH)

    embedder = build_embedding_adapter(
        config.get("adapters", {}).get("default_embedding_backend", "sentence-transformers")
    )
    store = build_vector_store(
        config.get("adapters", {}).get("default_vector_backend", "chroma")
    )

    rag = OscarRAG(
        config=config,
        ontology=Ontology(schema),
        graph=KnowledgeGraph(graph),
        embedder=embedder,
        store=store,
    )
    rag.build()
    _RAG_SINGLETON = rag
    return rag


def oscar_query(text: str, top_k: int = 10) -> dict:
    """Natural-language query interface over the Oscar knowledge graph."""
    return get_rag().query(text, top_k=top_k)


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------


EXAMPLE_QUERIES = [
    "황민호가 만든 하네스는 무엇인가?",
    "BloomLabs Content Harness가 사용하는 아키텍처 패턴과 발행 매체는?",
    "Claude Code Agent Teams를 활성화하려면 어떤 환경 변수가 필요한가?",
    "하네스 엔지니어링 패러다임은 어떤 흐름으로 진화했는가?",
    "A/B 실험에서 측정된 품질 지표 변화는?",
]


def _print_hit(hit: dict, indent: str = "    ") -> None:
    h = hit["hit"]
    print(f"{indent}- [{h['metadata'].get('kind')}] "
          f"score={h['score']:.4f} :: {h['document'][:120]}")


if __name__ == "__main__":
    print("=" * 72)
    print("Oscar RAG setup")
    print("=" * 72)
    rag = get_rag()

    for q in EXAMPLE_QUERIES:
        print("\n" + "-" * 72)
        print(f"Q: {q}")
        result = oscar_query(q, top_k=3)
        for collection, hits in result["results"].items():
            print(f"  [{collection}]")
            for h in hits:
                _print_hit(h)
    print("\nDone.")
