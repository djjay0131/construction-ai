"""JSON serialization for the object catalog.

Round-trip-safe by construction: every :class:`~app.core.catalog.catalog_builder.CatalogNode`
field is mapped 1:1 to JSON. ``save`` creates parent directories;
``load`` raises (does not swallow) on missing file or malformed JSON.

JSON shape (schema_version="4b-v1"):

    {
      "nodes": {
        "wall_0": {"id": "wall_0", "kind": "wall", "bbox_px": [...], ...},
        ...
      },
      "edges": [
        {"src": "wall_0", "dst": "wall_1", "kind": "CONNECTS_TO", "props": {}},
        ...
      ],
      "metadata": {"schema_version": "4b-v1", ...}
    }

Future format-experiment story: implement a ``NetworkxCatalogStore``
that reads the SAME JSON and returns a ``networkx.Graph`` view; the
JSON shape stays the contract.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.core.catalog.catalog_builder import Catalog, CatalogEdge, CatalogNode


class CatalogStore:
    """JSON persistence for :class:`Catalog` objects.

    Stateless — instantiate freely or hold one as a singleton; either works.
    """

    def save(self, catalog: Catalog, path: str | Path) -> None:
        """Write ``catalog`` to ``path`` as JSON. Creates parent dirs."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._to_dict(catalog)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)

    def load(self, path: str | Path) -> Catalog:
        """Read ``path`` and return the deserialised :class:`Catalog`.

        Raises ``FileNotFoundError`` if the file doesn't exist or
        ``json.JSONDecodeError`` if it can't be parsed. We don't swallow
        either — the caller decides whether to retry or surface a 5xx.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        return self._from_dict(payload)

    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(catalog: Catalog) -> dict[str, Any]:
        nodes = {nid: _node_to_dict(node) for nid, node in catalog.nodes.items()}
        edges = [_edge_to_dict(edge) for edge in catalog.edges]
        return {"nodes": nodes, "edges": edges, "metadata": catalog.metadata}

    @staticmethod
    def _from_dict(payload: dict[str, Any]) -> Catalog:
        nodes_raw: dict[str, dict[str, Any]] = payload.get("nodes", {})
        nodes = {nid: _node_from_dict(nd) for nid, nd in nodes_raw.items()}
        edges = [_edge_from_dict(ed) for ed in payload.get("edges", [])]
        metadata = payload.get("metadata", {})
        return Catalog(nodes=nodes, edges=edges, metadata=metadata)


def _node_to_dict(node: CatalogNode) -> dict[str, Any]:
    d = asdict(node)
    # asdict turns frozen dataclasses to dicts and tuples to lists; the
    # JSON round-trip will reconstruct via _node_from_dict.
    d["bbox_px"] = list(node.bbox_px)
    d["flags"] = list(node.flags)
    return d


def _node_from_dict(d: dict[str, Any]) -> CatalogNode:
    return CatalogNode(
        id=d["id"],
        kind=d["kind"],
        bbox_px=tuple(d["bbox_px"]),  # type: ignore[arg-type]
        confidence=float(d.get("confidence", 1.0)),
        length_in=d.get("length_in"),
        length_source=d.get("length_source"),
        ocr_dimension_in=d.get("ocr_dimension_in"),
        ocr_validation=d.get("ocr_validation"),
        width_in=d.get("width_in"),
        height_in=d.get("height_in"),
        flags=tuple(d.get("flags", [])),
    )


def _edge_to_dict(edge: CatalogEdge) -> dict[str, Any]:
    return {
        "src": edge.src,
        "dst": edge.dst,
        "kind": edge.kind,
        "props": dict(edge.props),
    }


def _edge_from_dict(d: dict[str, Any]) -> CatalogEdge:
    return CatalogEdge(
        src=d["src"],
        dst=d["dst"],
        kind=d["kind"],
        props=dict(d.get("props", {})),
    )
