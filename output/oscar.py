"""Top-level ``oscar`` package shim.

Enables ``from oscar import query, get_node, get_neighbors, get_subgraph``
when ``output/`` is on ``sys.path`` (or when this file is copied alongside
the caller).
"""
from oscar_api import query, get_node, get_neighbors, get_subgraph  # noqa: F401

__all__ = ["query", "get_node", "get_neighbors", "get_subgraph"]
