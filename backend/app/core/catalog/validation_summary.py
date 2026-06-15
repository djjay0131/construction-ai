"""Counts of OCR-vs-geometric validation buckets across a Catalog.

The takeoff API surfaces these counts in ``MaterialTakeoff.notes`` so
operators see at a glance how many walls were OCR-confirmed vs flagged.
Kept as a tiny frozen dataclass + pure function so consumers don't
have to repeat the counting logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.catalog.catalog_builder import Catalog


@dataclass(frozen=True)
class ValidationSummary:
    walls_total: int
    walls_confirmed: int
    walls_minor_discrepancy: int
    walls_mismatch: int
    walls_unvalidated: int  # walls with no OCR match (length_in known but no ocr_dimension)

    def __str__(self) -> str:
        return (
            f"{self.walls_total} walls — "
            f"{self.walls_confirmed} confirmed, "
            f"{self.walls_minor_discrepancy} minor discrepancy, "
            f"{self.walls_mismatch} mismatch, "
            f"{self.walls_unvalidated} unvalidated"
        )


def summarise_validation(catalog: Catalog) -> ValidationSummary:
    """Walk ``catalog.nodes`` and return per-bucket wall counts."""
    walls = [n for n in catalog.nodes.values() if n.kind == "wall"]
    confirmed = sum(1 for w in walls if w.ocr_validation == "confirmed")
    minor = sum(1 for w in walls if w.ocr_validation == "minor_discrepancy")
    mismatch = sum(1 for w in walls if w.ocr_validation == "mismatch")
    unvalidated = sum(1 for w in walls if w.ocr_validation is None)
    return ValidationSummary(
        walls_total=len(walls),
        walls_confirmed=confirmed,
        walls_minor_discrepancy=minor,
        walls_mismatch=mismatch,
        walls_unvalidated=unvalidated,
    )
