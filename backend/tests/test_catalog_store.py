"""Unit tests for ``app.core.catalog.catalog_store``."""

from __future__ import annotations

import json

import pytest

from app.core.catalog.catalog_builder import Catalog, CatalogEdge, CatalogNode
from app.core.catalog.catalog_store import CatalogStore


def _node(
    id_: str = "wall_0",
    kind: str = "wall",
    bbox=(0, 0, 100, 10),
    **extra,
) -> CatalogNode:
    return CatalogNode(id=id_, kind=kind, bbox_px=bbox, **extra)


def _make_catalog() -> Catalog:
    return Catalog(
        nodes={
            "wall_0": _node(
                length_in=150.3,
                length_source="geometric",
                ocr_dimension_in=150.0,
                ocr_validation="confirmed",
                flags=("ocr_geometry_mismatch",),  # intentionally exercise the tuple
            ),
            "door_0": _node(
                id_="door_0",
                kind="door",
                bbox=(40, 0, 60, 10),
                confidence=0.95,
                width_in=2.0,
                height_in=1.0,
            ),
        },
        edges=[
            CatalogEdge(src="wall_0", dst="door_0", kind="CONTAINS", props={"side": "left"}),
        ],
        metadata={"schema_version": "4b-v1", "extra": "data"},
    )


class TestSave:
    def test_save_creates_file(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        store.save(_make_catalog(), path)
        assert path.exists()

    def test_save_creates_parent_dirs(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "nested" / "dir" / "catalog.json"
        store.save(_make_catalog(), path)
        assert path.exists()

    def test_saved_json_is_pretty_printed(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        store.save(_make_catalog(), path)
        # Multi-line output (indented). One-line JSON would be a single line.
        assert path.read_text().count("\n") > 5

    def test_save_accepts_string_path(self, tmp_path):
        store = CatalogStore()
        path_str = str(tmp_path / "by_str.json")
        store.save(_make_catalog(), path_str)
        assert (tmp_path / "by_str.json").exists()


class TestLoad:
    def test_load_returns_equivalent_catalog(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        original = _make_catalog()
        store.save(original, path)
        loaded = store.load(path)
        assert loaded == original

    def test_load_returns_empty_catalog_when_empty(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "empty.json"
        store.save(Catalog(), path)
        loaded = store.load(path)
        assert loaded == Catalog()

    def test_load_missing_file_raises(self, tmp_path):
        store = CatalogStore()
        with pytest.raises(FileNotFoundError):
            store.load(tmp_path / "missing.json")

    def test_load_corrupt_json_raises(self, tmp_path):
        store = CatalogStore()
        bad = tmp_path / "bad.json"
        bad.write_text("not valid {")
        with pytest.raises(json.JSONDecodeError):
            store.load(bad)

    def test_load_accepts_string_path(self, tmp_path):
        store = CatalogStore()
        store.save(_make_catalog(), tmp_path / "c.json")
        loaded = store.load(str(tmp_path / "c.json"))
        assert loaded.nodes


class TestRoundTrip:
    def test_round_trip_preserves_all_node_fields(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        original = _make_catalog()
        store.save(original, path)
        loaded = store.load(path)

        # Spot-check key fields
        w0 = loaded.nodes["wall_0"]
        assert w0.length_in == pytest.approx(150.3)
        assert w0.ocr_validation == "confirmed"
        assert w0.flags == ("ocr_geometry_mismatch",)
        # bbox came back as a tuple, not a list
        assert isinstance(w0.bbox_px, tuple)

    def test_round_trip_preserves_edges(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        store.save(_make_catalog(), path)
        loaded = store.load(path)
        assert len(loaded.edges) == 1
        edge = loaded.edges[0]
        assert edge.kind == "CONTAINS"
        assert edge.props == {"side": "left"}

    def test_round_trip_preserves_metadata(self, tmp_path):
        store = CatalogStore()
        path = tmp_path / "catalog.json"
        store.save(_make_catalog(), path)
        loaded = store.load(path)
        assert loaded.metadata == {"schema_version": "4b-v1", "extra": "data"}
