"""Oscar Harness Knowledge Base — Python API wrapper.

Convenience facade exposing four functions:

    from oscar import query, get_node, get_neighbors, get_subgraph

Internally delegates retrieval to ``_workspace/scripts/setup_rag.py``
(hybrid vector + BM25 over the Oscar knowledge graph).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Locate the Oscar workspace and make setup_rag.py importable
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE = _ROOT / "_workspace"
_SCRIPTS = _WORKSPACE / "scripts"
_GRAPH_PATH = _WORKSPACE / "03_knowledge_graph.json"

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


# ---------------------------------------------------------------------------
# Lazy graph cache — used by get_node/get_neighbors/get_subgraph even when
# the heavy RAG (embeddings + vector store) hasn't been built yet.
# ---------------------------------------------------------------------------

_GRAPH_CACHE: Optional[Dict[str, Any]] = None


def _graph() -> Dict[str, Any]:
    global _GRAPH_CACHE
    if _GRAPH_CACHE is None:
        with open(_GRAPH_PATH, "r", encoding="utf-8") as f:
            _GRAPH_CACHE = json.load(f)
    return _GRAPH_CACHE


def _index_by(field: str) -> Dict[str, Dict[str, Any]]:
    return {n[field]: n for n in _graph()["nodes"] if field in n}


def _resolve_node(ref: str) -> Optional[Dict[str, Any]]:
    """Accept node_id (node_001), entity_id (E001), URI, or label."""
    if not ref:
        return None
    by_id = _index_by("id")
    if ref in by_id:
        return by_id[ref]
    by_eid = _index_by("entity_id")
    if ref in by_eid:
        return by_eid[ref]
    by_uri = _index_by("uri")
    if ref in by_uri:
        return by_uri[ref]
    target = ref.strip().lower()
    for n in _graph()["nodes"]:
        if n.get("label", "").lower() == target:
            return n
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def query(text: str, top_k: int = 10) -> Dict[str, Any]:
    """Natural-language query over the Oscar KB.

    Hybrid (vector + BM25) retrieval with ontology-aware context expansion.
    Returns ``{"query", "top_k", "results": {"nodes": [...], "edges": [...],
    "subgraphs": [...]}}``.
    """
    from setup_rag import oscar_query  # lazy: builds the index on first call
    return oscar_query(text, top_k=top_k)


def get_node(ref: str) -> Optional[Dict[str, Any]]:
    """Look up a node by ``entity_id`` (E001), ``node_id`` (node_001),
    URI, or label. Returns the raw node dict or ``None``."""
    return _resolve_node(ref)


def get_neighbors(ref: str, hops: int = 1,
                  direction: str = "both") -> List[Dict[str, Any]]:
    """Return neighboring nodes within ``hops`` (BFS).

    Each item: ``{"edge": {...}, "node": {...}, "direction": "out"|"in"}``.
    ``direction`` may be ``"out"``, ``"in"``, or ``"both"`` (default).
    """
    node = _resolve_node(ref)
    if node is None:
        return []
    g = _graph()
    by_id = {n["id"]: n for n in g["nodes"]}
    out_edges: Dict[str, List[dict]] = {}
    in_edges: Dict[str, List[dict]] = {}
    for e in g["edges"]:
        out_edges.setdefault(e["source"], []).append(e)
        in_edges.setdefault(e["target"], []).append(e)

    seen = {node["id"]}
    frontier = [node["id"]]
    out: List[Dict[str, Any]] = []
    for _ in range(max(1, hops)):
        nxt: List[str] = []
        for nid in frontier:
            if direction in ("out", "both"):
                for e in out_edges.get(nid, []):
                    if e["target"] not in seen:
                        seen.add(e["target"])
                        nxt.append(e["target"])
                        out.append({"edge": e, "node": by_id[e["target"]],
                                    "direction": "out"})
            if direction in ("in", "both"):
                for e in in_edges.get(nid, []):
                    if e["source"] not in seen:
                        seen.add(e["source"])
                        nxt.append(e["source"])
                        out.append({"edge": e, "node": by_id[e["source"]],
                                    "direction": "in"})
        frontier = nxt
    return out


def get_subgraph(ref: str, hops: int = 2) -> Dict[str, Any]:
    """Return an induced subgraph centered on ``ref`` within ``hops``.

    Result shape: ``{"center": {...}, "nodes": [...], "edges": [...]}``.
    """
    center = _resolve_node(ref)
    if center is None:
        return {"center": None, "nodes": [], "edges": []}
    nbrs = get_neighbors(center["id"], hops=hops, direction="both")
    node_ids = {center["id"]} | {n["node"]["id"] for n in nbrs}
    nodes = [n for n in _graph()["nodes"] if n["id"] in node_ids]
    edges = [e for e in _graph()["edges"]
             if e["source"] in node_ids and e["target"] in node_ids]
    return {"center": center, "nodes": nodes, "edges": edges}


__all__ = ["query", "get_node", "get_neighbors", "get_subgraph"]


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Oscar harness KB CLI")
    parser.add_argument("command", choices=["query", "node", "neighbors", "subgraph"])
    parser.add_argument("arg", help="query text or node reference")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--hops", type=int, default=1)
    args = parser.parse_args()

    if args.command == "query":
        print(json.dumps(query(args.arg, top_k=args.top_k),
                         ensure_ascii=False, indent=2))
    elif args.command == "node":
        print(json.dumps(get_node(args.arg), ensure_ascii=False, indent=2))
    elif args.command == "neighbors":
        print(json.dumps(get_neighbors(args.arg, hops=args.hops),
                         ensure_ascii=False, indent=2))
    elif args.command == "subgraph":
        print(json.dumps(get_subgraph(args.arg, hops=args.hops),
                         ensure_ascii=False, indent=2))
