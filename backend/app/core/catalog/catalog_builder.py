"""Object catalog construction.

Builds a :class:`Catalog` (dict of :class:`CatalogNode` + list of
:class:`CatalogEdge`) from the raster pipeline's outputs:

* wall segments (from Sprint 3b :class:`WallLineExtractor`)
* YOLO detections (Sprint 3b :class:`Detection`)
* parsed OCR dimensions (Sprint 4a :class:`ParsedDimension`)

Plus an optional ``scale_px_per_in`` (from Sprint 3b
:class:`ScaleDetector`) so wall lengths get computed in inches.

When OCR dimensions are attached to a wall, the builder validates them
against the geometric length:

* ``<10%`` difference → ``ocr_validation="confirmed"``
* ``10–15%`` → ``"minor_discrepancy"``
* ``>15%`` → ``"mismatch"`` plus ``"ocr_geometry_mismatch"`` flag

The output is plain Python data (dataclasses + dict). Serialisation to
JSON lives in :mod:`app.core.catalog.catalog_store`. NetworkX is
explicitly deferred per the parent Sprint 4 spec's "Storage Format
Experiment" section.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.core.catalog.spatial_association import (
    SpatialAssociator,
    _bbox_centroid,
)
from app.core.cv.dimension_extractor import ParsedDimension
from app.core.cv.wall_line_extractor import Detection

BBox = tuple[int, int, int, int]
PixelPoint = tuple[int, int]
PixelSegment = tuple[PixelPoint, PixelPoint]

WALL_LABEL = "wall"
OPENING_LABELS = {"door", "window", "opening"}


@dataclass(frozen=True)
class CatalogNode:
    id: str
    kind: str  # "wall" | "door" | "window" | "opening"
    bbox_px: BBox
    confidence: float = 1.0
    length_in: float | None = None
    length_source: str | None = None  # "geometric" | "ocr_fallback" | None
    ocr_dimension_in: float | None = None
    ocr_validation: str | None = None  # "confirmed" | "minor_discrepancy" | "mismatch"
    width_in: float | None = None
    height_in: float | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CatalogEdge:
    src: str
    dst: str
    kind: str  # "CONNECTS_TO" | "CONTAINS"
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class Catalog:
    nodes: dict[str, CatalogNode] = field(default_factory=dict)
    edges: list[CatalogEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _segment_bbox(seg: PixelSegment) -> BBox:
    (x1, y1), (x2, y2) = seg
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _segment_length_px(seg: PixelSegment) -> float:
    (x1, y1), (x2, y2) = seg
    return math.hypot(x2 - x1, y2 - y1)


def _points_close(p1: PixelPoint, p2: PixelPoint, tol: float) -> bool:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1]) <= tol


def _point_in_bbox(point: tuple[float, float], bbox: BBox) -> bool:
    px, py = point
    x1, y1, x2, y2 = bbox
    return x1 <= px <= x2 and y1 <= py <= y2


class ObjectCatalogBuilder:
    """Build a :class:`Catalog` from raster pipeline outputs."""

    def __init__(
        self,
        associator: SpatialAssociator | None = None,
        connection_tolerance_px: float = 10.0,
        confirm_threshold: float = 0.10,
        mismatch_threshold: float = 0.15,
    ) -> None:
        if connection_tolerance_px < 0:
            raise ValueError(
                f"connection_tolerance_px must be non-negative; got {connection_tolerance_px}"
            )
        if not (0 < confirm_threshold < mismatch_threshold):
            raise ValueError(
                f"thresholds must satisfy 0 < confirm < mismatch; got "
                f"{confirm_threshold}, {mismatch_threshold}"
            )
        self.associator = associator or SpatialAssociator()
        self.connection_tolerance_px = connection_tolerance_px
        self.confirm_threshold = confirm_threshold
        self.mismatch_threshold = mismatch_threshold

    def build(
        self,
        wall_segments: Sequence[PixelSegment],
        detections: Sequence[Detection],
        dimensions: Sequence[ParsedDimension],
        scale_px_per_in: float | None = None,
    ) -> Catalog:
        catalog = Catalog(metadata={"schema_version": "4b-v1"})

        # 1. Wall nodes
        wall_segments = list(wall_segments)
        wall_ids: list[str] = []
        for i, seg in enumerate(wall_segments):
            wid = f"wall_{i}"
            wall_ids.append(wid)
            length_in: float | None = None
            length_source: str | None = None
            if scale_px_per_in is not None and scale_px_per_in > 0:
                length_in = _segment_length_px(seg) / scale_px_per_in
                length_source = "geometric"
            catalog.nodes[wid] = CatalogNode(
                id=wid,
                kind="wall",
                bbox_px=_segment_bbox(seg),
                length_in=length_in,
                length_source=length_source,
            )

        # 2. Opening nodes (doors, windows, openings)
        opening_ids: list[str] = []
        opening_counter: dict[str, int] = {}
        for det in detections:
            if det.label not in OPENING_LABELS:
                continue
            idx = opening_counter.get(det.label, 0)
            opening_counter[det.label] = idx + 1
            oid = f"{det.label}_{idx}"
            opening_ids.append(oid)
            width_px = det.bbox[2] - det.bbox[0]
            height_px = det.bbox[3] - det.bbox[1]
            width_in = (
                width_px / scale_px_per_in
                if scale_px_per_in is not None and scale_px_per_in > 0
                else None
            )
            height_in = (
                height_px / scale_px_per_in
                if scale_px_per_in is not None and scale_px_per_in > 0
                else None
            )
            catalog.nodes[oid] = CatalogNode(
                id=oid,
                kind=det.label,
                bbox_px=det.bbox,
                confidence=det.confidence,
                width_in=width_in,
                height_in=height_in,
            )

        # 3. CONNECTS_TO edges (wall–wall)
        for i in range(len(wall_segments)):
            for j in range(i + 1, len(wall_segments)):
                if self._walls_connect(wall_segments[i], wall_segments[j]):
                    catalog.edges.append(
                        CatalogEdge(src=wall_ids[i], dst=wall_ids[j], kind="CONNECTS_TO")
                    )

        # 4. CONTAINS edges (wall–opening)
        for oid in opening_ids:
            opening_node = catalog.nodes[oid]
            ocx, ocy = _bbox_centroid(opening_node.bbox_px)
            best_wall_id = self._wall_containing_opening(
                (ocx, ocy), wall_ids, catalog
            )
            if best_wall_id is not None:
                catalog.edges.append(
                    CatalogEdge(src=best_wall_id, dst=oid, kind="CONTAINS")
                )

        # 5. Attach OCR dimensions + validate
        all_nodes = [catalog.nodes[i] for i in wall_ids + opening_ids]
        pairs = self.associator.associate(dimensions, all_nodes)
        for node_id, dim in pairs:
            node = catalog.nodes[node_id]
            if node.kind == "wall":
                catalog.nodes[node_id] = self._validate_wall_dim(node, dim)
            # Openings could attach OCR (door width, etc.); not in 4b scope.

        return catalog

    def _walls_connect(self, a: PixelSegment, b: PixelSegment) -> bool:
        tol = self.connection_tolerance_px
        endpoints_a = [a[0], a[1]]
        endpoints_b = [b[0], b[1]]
        for pa in endpoints_a:
            for pb in endpoints_b:
                if _points_close(pa, pb, tol):
                    return True
        return False

    @staticmethod
    def _wall_containing_opening(
        opening_centroid: tuple[float, float],
        wall_ids: Sequence[str],
        catalog: Catalog,
    ) -> str | None:
        for wid in wall_ids:
            if _point_in_bbox(opening_centroid, catalog.nodes[wid].bbox_px):
                return wid
        return None

    def _validate_wall_dim(
        self, wall: CatalogNode, dim: ParsedDimension
    ) -> CatalogNode:
        new_flags = list(wall.flags)
        validation: str | None
        if wall.length_in is None or wall.length_in <= 0:
            validation = None
        else:
            diff = abs(dim.inches - wall.length_in) / wall.length_in
            if diff < self.confirm_threshold:
                validation = "confirmed"
            elif diff < self.mismatch_threshold:
                validation = "minor_discrepancy"
            else:
                validation = "mismatch"
                if "ocr_geometry_mismatch" not in new_flags:
                    new_flags.append("ocr_geometry_mismatch")
        return CatalogNode(
            id=wall.id,
            kind=wall.kind,
            bbox_px=wall.bbox_px,
            confidence=wall.confidence,
            length_in=wall.length_in,
            length_source=wall.length_source,
            ocr_dimension_in=dim.inches,
            ocr_validation=validation,
            width_in=wall.width_in,
            height_in=wall.height_in,
            flags=tuple(new_flags),
        )
