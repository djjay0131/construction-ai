"""Unit tests for ``app.core.catalog.spatial_association``."""

from __future__ import annotations

import pytest

from app.core.catalog.catalog_builder import CatalogNode
from app.core.catalog.spatial_association import SpatialAssociator
from app.core.cv.dimension_extractor import ParsedDimension


def _dim(text: str, bbox, inches: float, confidence: float = 0.9) -> ParsedDimension:
    return ParsedDimension(text=text, bbox=bbox, inches=inches, confidence=confidence)


def _node(id_: str, bbox, kind: str = "wall") -> CatalogNode:
    return CatalogNode(id=id_, kind=kind, bbox_px=bbox)


class TestConstructorValidation:
    def test_zero_distance_raises(self):
        with pytest.raises(ValueError, match="positive"):
            SpatialAssociator(max_distance_px=0)

    def test_negative_distance_raises(self):
        with pytest.raises(ValueError, match="positive"):
            SpatialAssociator(max_distance_px=-1)


class TestEmptyCandidates:
    def test_empty_candidates_returns_empty(self):
        a = SpatialAssociator()
        result = a.associate([_dim("12'", (0, 0, 50, 20), 144.0)], [])
        assert result == []


class TestSingleCandidateWithinDistance:
    def test_single_dim_pairs_with_only_candidate(self):
        a = SpatialAssociator(max_distance_px=100)
        # Dimension centroid (25, 10); candidate centroid (15, 10). Distance 10.
        dim = _dim('12"', bbox=(0, 0, 50, 20), inches=12.0)
        node = _node("wall_0", (0, 0, 30, 20))
        result = a.associate([dim], [node])
        assert result == [("wall_0", dim)]


class TestNearestCandidateWins:
    def test_three_candidates_picks_nearest(self):
        a = SpatialAssociator(max_distance_px=500)
        # Dim centroid (50, 50)
        dim = _dim('12"', bbox=(40, 40, 60, 60), inches=12.0)
        near = _node("wall_near", (45, 45, 55, 55))    # centroid (50, 50)
        mid = _node("wall_mid", (100, 100, 110, 110))  # centroid (105, 105)
        far = _node("wall_far", (300, 300, 310, 310))  # centroid (305, 305)
        result = a.associate([dim], [mid, far, near])
        assert result == [("wall_near", dim)]


class TestDistanceCap:
    def test_dim_beyond_threshold_is_dropped(self):
        a = SpatialAssociator(max_distance_px=50)
        dim = _dim('12"', bbox=(0, 0, 20, 20), inches=12.0)
        # Candidate centroid (200, 200) — well beyond 50 px.
        node = _node("wall_0", (190, 190, 210, 210))
        assert a.associate([dim], [node]) == []


class TestTieBreaking:
    def test_equidistant_candidates_break_by_larger_area(self):
        a = SpatialAssociator(max_distance_px=500)
        dim = _dim('12"', bbox=(0, 0, 20, 20), inches=12.0)
        # Two candidates, both with centroid (50, 10) → equal distance to dim.
        small = _node("wall_small", (45, 5, 55, 15))    # area 100
        large = _node("wall_large", (10, 0, 90, 20))    # area 80*20=1600
        result = a.associate([dim], [small, large])
        # large wins on area
        assert result == [("wall_large", dim)]

    def test_equal_area_breaks_by_lexicographic_id(self):
        a = SpatialAssociator(max_distance_px=500)
        dim = _dim('12"', bbox=(0, 0, 20, 20), inches=12.0)
        n_a = _node("a", (40, 0, 60, 20))   # centroid (50, 10), area 400
        n_b = _node("b", (40, 0, 60, 20))   # same bbox shape, centroid same
        # Pass n_b first to verify we don't just keep the first one seen.
        result = a.associate([dim], [n_b, n_a])
        assert result == [("a", dim)]


class TestMultipleDimensions:
    def test_each_dim_paired_independently(self):
        a = SpatialAssociator(max_distance_px=200)
        d1 = _dim("d1", bbox=(0, 0, 20, 20), inches=10.0)
        d2 = _dim("d2", bbox=(200, 200, 220, 220), inches=20.0)
        n1 = _node("wall_left", (5, 5, 25, 25))
        n2 = _node("wall_right", (210, 210, 230, 230))
        result = a.associate([d1, d2], [n1, n2])
        ids = [pair[0] for pair in result]
        assert ids == ["wall_left", "wall_right"]
