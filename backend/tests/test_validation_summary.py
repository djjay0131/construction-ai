"""Unit tests for ``app.core.catalog.validation_summary``."""

from __future__ import annotations

from app.core.catalog.catalog_builder import Catalog, CatalogNode
from app.core.catalog.validation_summary import (
    ValidationSummary,
    summarise_validation,
)


def _wall(id_: str, validation: str | None) -> CatalogNode:
    return CatalogNode(
        id=id_,
        kind="wall",
        bbox_px=(0, 0, 10, 10),
        length_in=10.0,
        length_source="geometric",
        ocr_validation=validation,
    )


def _door(id_: str = "door_0") -> CatalogNode:
    return CatalogNode(id=id_, kind="door", bbox_px=(0, 0, 5, 10))


class TestEmptyCatalog:
    def test_empty_catalog_returns_all_zeros(self):
        s = summarise_validation(Catalog())
        assert s == ValidationSummary(0, 0, 0, 0, 0)


class TestOnlyDoors:
    def test_doors_dont_count_as_walls(self):
        cat = Catalog(nodes={"door_0": _door(), "door_1": _door("door_1")})
        s = summarise_validation(cat)
        assert s.walls_total == 0


class TestBucketCounts:
    def test_counts_each_validation_state(self):
        cat = Catalog(
            nodes={
                "wall_0": _wall("wall_0", "confirmed"),
                "wall_1": _wall("wall_1", "confirmed"),
                "wall_2": _wall("wall_2", "minor_discrepancy"),
                "wall_3": _wall("wall_3", "mismatch"),
                "wall_4": _wall("wall_4", None),
            }
        )
        s = summarise_validation(cat)
        assert s.walls_total == 5
        assert s.walls_confirmed == 2
        assert s.walls_minor_discrepancy == 1
        assert s.walls_mismatch == 1
        assert s.walls_unvalidated == 1


class TestDataclassImmutability:
    def test_validation_summary_is_frozen(self):
        s = ValidationSummary(1, 1, 0, 0, 0)
        import pytest
        with pytest.raises(AttributeError):
            s.walls_total = 99  # type: ignore[misc]


class TestStringRepresentation:
    def test_str_includes_all_buckets(self):
        s = ValidationSummary(5, 2, 1, 1, 1)
        out = str(s)
        assert "5 walls" in out
        assert "2 confirmed" in out
        assert "1 minor discrepancy" in out
        assert "1 mismatch" in out
        assert "1 unvalidated" in out

    def test_str_for_empty_summary(self):
        out = str(ValidationSummary(0, 0, 0, 0, 0))
        assert "0 walls" in out
