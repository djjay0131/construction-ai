"""Spatial association of OCR dimensions to architectural elements.

Given a list of :class:`~app.core.cv.dimension_extractor.ParsedDimension`s
and a list of candidate :class:`~app.core.catalog.catalog_builder.CatalogNode`s,
pair each dimension with the nearest candidate by bbox-centroid distance,
dropping dimensions whose nearest candidate is beyond ``max_distance_px``.

Ambiguous ties (two candidates equidistant) are broken by the larger
bbox area — a wall is more likely than a window at the same distance.
Equal areas: lexicographically smaller id wins (deterministic).
"""

from __future__ import annotations

import math
from typing import Sequence, TYPE_CHECKING

from app.core.cv.dimension_extractor import ParsedDimension

if TYPE_CHECKING:  # pragma: no cover - avoids circular import at runtime
    from app.core.catalog.catalog_builder import CatalogNode

BBox = tuple[int, int, int, int]


def _bbox_centroid(bbox: BBox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _bbox_area(bbox: BBox) -> int:
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


class SpatialAssociator:
    """Assign parsed dimensions to the nearest architectural element."""

    def __init__(self, max_distance_px: float = 200.0) -> None:
        if max_distance_px <= 0:
            raise ValueError(
                f"max_distance_px must be positive; got {max_distance_px}"
            )
        self.max_distance_px = max_distance_px

    def associate(
        self,
        dimensions: Sequence[ParsedDimension],
        candidates: Sequence["CatalogNode"],
    ) -> list[tuple[str, ParsedDimension]]:
        """Return ``[(candidate_id, dimension), ...]`` for the dimensions
        whose nearest candidate is within ``max_distance_px``."""
        if not candidates:
            return []
        out: list[tuple[str, ParsedDimension]] = []
        for dim in dimensions:
            best = self._nearest(dim, candidates)
            if best is not None:
                out.append((best, dim))
        return out

    def _nearest(
        self,
        dim: ParsedDimension,
        candidates: Sequence["CatalogNode"],
    ) -> str | None:
        dcx, dcy = _bbox_centroid(dim.bbox)
        best_id: str | None = None
        best_dist = math.inf
        best_area = -1

        for cand in candidates:
            ccx, ccy = _bbox_centroid(cand.bbox_px)
            dist = math.hypot(dcx - ccx, dcy - ccy)
            if dist > self.max_distance_px:
                continue
            area = _bbox_area(cand.bbox_px)
            replace = False
            if dist < best_dist - 1e-9:
                replace = True
            elif math.isclose(dist, best_dist):
                if area > best_area:
                    replace = True
                elif area == best_area and (best_id is None or cand.id < best_id):
                    replace = True
            if replace:
                best_id = cand.id
                best_dist = dist
                best_area = area
        return best_id
