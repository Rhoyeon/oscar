"""Oscar Knowledge Base — public Python API.

Thin, easy-to-use facade over the full RAG pipeline implemented in
``_workspace/scripts/setup_rag.py``. Re-exports four primitives:

    from oscar import query, get_node, get_neighbors, get_subgraph

The first call lazily builds the index (embeddings + Chroma + BM25). All
subsequent calls reuse a process-wide singleton.

Example:
    >>> from oscar import query, get_node, get_neighbors
    >>> hits = query("황민호가 만든 하네스는?", top_k=3)
    >>> get_node("revfactory/harness")["properties"]["version"]
    'v1.0.1'
    >>> [n["label"] for _e, n, _d in get_neighbors("BloomLabs Content Harness")]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Wire up the underlying RAG implementation in _workspace/scripts/setup_rag.py
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
_RAG_SCRIPTS = _REPO_ROOT / "_workspace" / "scripts"
if str(_RAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_RAG_SCRIPTS))

import setup_rag  # noqa: E402  (sys.path adjusted above)


__all__ = [
    "query",
    "get_node",
    "get_neighbors",
    "get_subgraph",
    "list_classes",
    "rag",
]


def rag() -> "setup_rag.OscarRAG":
    """Return the lazily-built singleton ``OscarRAG`` instance."""
    return setup_rag.get_rag()


# ---------------------------------------------------------------------------
# Internal lookup helpers
# ---------------------------------------------------------------------------


def _resolve_node(identifier: str) -> Optional[dict]:
    """Resolve a node by label, entity_id (E###), node id (node_###), or URI."""
    g = rag().graph
    if identifier in g.node_by_id:
        return g.node_by_id[identifier]
    needle = identifier.strip().lower()
    for n in g.nodes:
        if n.get("entity_id", "").lower() == needle:
            return n
        if n.get("uri", "").lower() == needle:
            return n
        if n.get("label", "").lower() == needle:
            return n
    # Fallback: case-insensitive substring match on label
    for n in g.nodes:
        if needle in n.get("label", "").lower():
            return n
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def query(text: str, top_k: int = 10) -> Dict[str, Any]:
    """Natural-language hybrid search over nodes / edges / subgraphs.

    Returns a dict shaped as::

        {"query": str, "top_k": int,
         "results": {"nodes": [...], "edges": [...], "subgraphs": [...]}}
    """
    return setup_rag.oscar_query(text, top_k=top_k)


def get_node(identifier: str) -> Optional[dict]:
    """Look up a single node by label / entity_id / node_id / URI."""
    return _resolve_node(identifier)


def get_neighbors(
    identifier: str, hops: int = 1
) -> List[Tuple[dict, dict, str]]:
    """Return the n-hop neighborhood as ``[(edge, neighbor_node, direction), ...]``.

    ``direction`` is ``"out"`` (identifier -> neighbor) or ``"in"`` (neighbor -> identifier).
    """
    node = _resolve_node(identifier)
    if node is None:
        return []
    return rag().graph.neighbors(node["id"], hops=hops)


def get_subgraph(identifier: str, hops: int = 2) -> Dict[str, Any]:
    """Return a serializable subgraph around ``identifier`` (center + n-hop frontier).

    Output schema::

        {"center": <node>, "hops": int,
         "nodes": [<node>, ...], "edges": [<edge>, ...]}
    """
    node = _resolve_node(identifier)
    if node is None:
        return {"center": None, "hops": hops, "nodes": [], "edges": []}
    frontier = rag().graph.neighbors(node["id"], hops=hops)
    nodes = {node["id"]: node}
    edges: Dict[str, dict] = {}
    for edge, nbr, _direction in frontier:
        nodes[nbr["id"]] = nbr
        edges[edge["id"]] = edge
    return {
        "center": node,
        "hops": hops,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def list_classes() -> List[dict]:
    """Return all ontology classes (id, name, parent, description)."""
    return rag().ontology.schema["classes"]


# ---------------------------------------------------------------------------
# CLI: ``python oscar_api.py "내 질문"``
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    if len(sys.argv) < 2:
        print("usage: python oscar_api.py <natural-language-question> [top_k]")
        sys.exit(1)
    q_text = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(json.dumps(query(q_text, top_k=k), ensure_ascii=False, indent=2))
