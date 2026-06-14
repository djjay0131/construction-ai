"""Unit tests for ``app.core.catalog.catalog_builder``."""

from __future__ import annotations

import pytest

from app.core.catalog.catalog_builder import (
    Catalog,
    CatalogEdge,
    CatalogNode,
    ObjectCatalogBuilder,
)
from app.core.cv.dimension_extractor import ParsedDimension
from app.core.cv.wall_line_extractor import Detection


def _det(label: str, bbox, confidence: float = 0.9) -> Detection:
    return Detection(label=label, bbox=tuple(bbox), confidence=confidence)


def _dim(text: str, bbox, inches: float, confidence: float = 0.9) -> ParsedDimension:
    return ParsedDimension(text=text, bbox=bbox, inches=inches, confidence=confidence)


class TestConstructorValidation:
    def test_negative_tolerance_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            ObjectCatalogBuilder(connection_tolerance_px=-1)

    def test_zero_confirm_threshold_raises(self):
        with pytest.raises(ValueError, match="thresholds"):
            ObjectCatalogBuilder(confirm_threshold=0, mismatch_threshold=0.15)

    def test_confirm_greater_than_mismatch_raises(self):
        with pytest.raises(ValueError, match="thresholds"):
            ObjectCatalogBuilder(confirm_threshold=0.5, mismatch_threshold=0.2)


class TestEmptyInputs:
    def test_no_inputs_returns_empty_catalog_with_schema_version(self):
        cat = ObjectCatalogBuilder().build([], [], [])
        assert cat.nodes == {}
        assert cat.edges == []
        assert cat.metadata == {"schema_version": "4b-v1"}


class TestWallNodes:
    def test_wall_with_scale_has_geometric_length(self):
        b = ObjectCatalogBuilder()
        # 100 px horizontal wall, scale 10 px/in → 10 in.
        cat = b.build(
            wall_segments=[((0, 0), (100, 0))],
            detections=[],
            dimensions=[],
            scale_px_per_in=10.0,
        )
        w0 = cat.nodes["wall_0"]
        assert w0.kind == "wall"
        assert w0.length_in == pytest.approx(10.0)
        assert w0.length_source == "geometric"

    def test_wall_without_scale_has_no_length(self):
        cat = ObjectCatalogBuilder().build(
            wall_segments=[((0, 0), (100, 0))],
            detections=[],
            dimensions=[],
        )
        w0 = cat.nodes["wall_0"]
        assert w0.length_in is None
        assert w0.length_source is None


class TestOpeningNodes:
    def test_door_node_dimensions_from_bbox(self):
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[],
            detections=[_det("door", (0, 0, 40, 80), confidence=0.95)],
            dimensions=[],
            scale_px_per_in=10.0,
        )
        d0 = cat.nodes["door_0"]
        assert d0.kind == "door"
        assert d0.confidence == 0.95
        assert d0.width_in == pytest.approx(4.0)
        assert d0.height_in == pytest.approx(8.0)

    def test_multiple_same_type_get_indexed_ids(self):
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[],
            detections=[
                _det("door", (0, 0, 10, 10)),
                _det("door", (50, 50, 60, 60)),
                _det("window", (100, 0, 110, 10)),
            ],
            dimensions=[],
        )
        assert "door_0" in cat.nodes
        assert "door_1" in cat.nodes
        assert "window_0" in cat.nodes

    def test_unknown_labels_ignored(self):
        # Walls come from wall_segments, not "wall"-labelled detections.
        # Anything outside {door, window, opening} is dropped.
        cat = ObjectCatalogBuilder().build(
            wall_segments=[],
            detections=[_det("ceiling_fan", (0, 0, 10, 10))],
            dimensions=[],
        )
        assert cat.nodes == {}


class TestConnectsToEdges:
    def test_two_walls_sharing_endpoint_connect(self):
        b = ObjectCatalogBuilder(connection_tolerance_px=10)
        # Wall A: (0,0)-(100,0); Wall B: (100,0)-(100,100). Share (100,0).
        cat = b.build(
            wall_segments=[((0, 0), (100, 0)), ((100, 0), (100, 100))],
            detections=[],
            dimensions=[],
        )
        connects = [e for e in cat.edges if e.kind == "CONNECTS_TO"]
        assert len(connects) == 1
        assert connects[0].src == "wall_0"
        assert connects[0].dst == "wall_1"

    def test_walls_outside_tolerance_dont_connect(self):
        b = ObjectCatalogBuilder(connection_tolerance_px=5)
        # Walls 100 px apart — well beyond 5 px tolerance.
        cat = b.build(
            wall_segments=[((0, 0), (50, 0)), ((150, 0), (200, 0))],
            detections=[],
            dimensions=[],
        )
        assert not [e for e in cat.edges if e.kind == "CONNECTS_TO"]


class TestContainsEdges:
    def test_door_whose_centroid_is_inside_wall_bbox_is_contained(self):
        b = ObjectCatalogBuilder()
        # Wall bbox spans (0, 0) to (100, 10). Door centroid (50, 5) is inside.
        cat = b.build(
            wall_segments=[((0, 0), (100, 10))],
            detections=[_det("door", (40, 0, 60, 10))],
            dimensions=[],
        )
        contains = [e for e in cat.edges if e.kind == "CONTAINS"]
        assert len(contains) == 1
        assert contains[0].src == "wall_0"
        assert contains[0].dst == "door_0"

    def test_door_outside_any_wall_bbox_has_no_contains_edge(self):
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[((0, 0), (50, 0))],
            detections=[_det("door", (1000, 1000, 1010, 1010))],
            dimensions=[],
        )
        assert not [e for e in cat.edges if e.kind == "CONTAINS"]


class TestOcrValidation:
    def test_confirmed_when_diff_under_10pct(self):
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[((0, 0), (1503, 0))],  # 1503 px / 10 = 150.3 in
            detections=[],
            dimensions=[_dim('12\'-6"', bbox=(700, 0, 800, 20), inches=150.0)],
            scale_px_per_in=10.0,
        )
        w0 = cat.nodes["wall_0"]
        assert w0.ocr_dimension_in == pytest.approx(150.0)
        assert w0.ocr_validation == "confirmed"
        assert "ocr_geometry_mismatch" not in w0.flags

    def test_mismatch_when_diff_over_15pct(self):
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[((0, 0), (1000, 0))],  # 100 in at scale 10
            detections=[],
            dimensions=[_dim('200"', bbox=(400, 0, 600, 20), inches=200.0)],
            scale_px_per_in=10.0,
        )
        w0 = cat.nodes["wall_0"]
        assert w0.ocr_validation == "mismatch"
        assert "ocr_geometry_mismatch" in w0.flags

    def test_minor_discrepancy_between_thresholds(self):
        b = ObjectCatalogBuilder()
        # 100 in geometric, 112 in OCR → 12% diff → "minor_discrepancy"
        cat = b.build(
            wall_segments=[((0, 0), (1000, 0))],
            detections=[],
            dimensions=[_dim('112"', bbox=(400, 0, 600, 20), inches=112.0)],
            scale_px_per_in=10.0,
        )
        assert cat.nodes["wall_0"].ocr_validation == "minor_discrepancy"

    def test_no_validation_when_length_in_is_none(self):
        # No scale → no geometric length → cannot validate.
        b = ObjectCatalogBuilder()
        cat = b.build(
            wall_segments=[((0, 0), (1000, 0))],
            detections=[],
            dimensions=[_dim('100"', bbox=(400, 0, 600, 20), inches=100.0)],
        )
        w0 = cat.nodes["wall_0"]
        assert w0.length_in is None
        assert w0.ocr_dimension_in == pytest.approx(100.0)
        assert w0.ocr_validation is None


class TestDataclassInvariants:
    def test_catalog_node_is_frozen(self):
        n = CatalogNode(id="x", kind="wall", bbox_px=(0, 0, 10, 10))
        with pytest.raises(AttributeError):
            n.kind = "door"  # type: ignore[misc]

    def test_catalog_edge_is_frozen(self):
        e = CatalogEdge(src="a", dst="b", kind="CONNECTS_TO")
        with pytest.raises(AttributeError):
            e.kind = "CONTAINS"  # type: ignore[misc]

    def test_empty_catalog_default_factory(self):
        c = Catalog()
        assert c.nodes == {}
        assert c.edges == []
        assert c.metadata == {}
