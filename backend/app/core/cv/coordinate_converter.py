"""Pixel→inches translation for raster-pipeline wall segments.

A small helper that turns ``[(start_px, end_px), ...]`` into the project's
existing ``WallElement[]`` shape using a known pixels-per-inch scale.
Reuses ``app.core.parsers.dxf_parser.WallElement`` unchanged — the whole
point of the parser-interface contract is that the downstream
``LumberCalculator`` (KG-backed since Sprint 2a) stays oblivious to whether
walls came from DXF, vector PDF, or raster.
"""

from __future__ import annotations

import logging
from typing import Iterable, Tuple

from app.core.parsers.dxf_parser import WallElement

logger = logging.getLogger(__name__)

PixelSegment = Tuple[Tuple[float, float], Tuple[float, float]]


class CoordinateConverter:
    """Translate pixel-space line segments into the project's WallElement[] shape."""

    def __init__(
        self,
        scale_px_per_in: float,
        default_thickness_in: float = 4.0,
        default_layer: str = "raster",
    ) -> None:
        if scale_px_per_in <= 0:
            raise ValueError(
                f"scale_px_per_in must be positive; got {scale_px_per_in}"
            )
        self.scale_px_per_in = scale_px_per_in
        self.default_thickness_in = default_thickness_in
        self.default_layer = default_layer

    def to_wall_elements(
        self, segments_px: Iterable[PixelSegment]
    ) -> list[WallElement]:
        """Convert pixel-coordinate line segments to ``WallElement[]``."""
        return [self._make_wall(start_px, end_px) for start_px, end_px in segments_px]

    def _make_wall(
        self,
        start_px: Tuple[float, float],
        end_px: Tuple[float, float],
    ) -> WallElement:
        start_in = (
            start_px[0] / self.scale_px_per_in,
            start_px[1] / self.scale_px_per_in,
        )
        end_in = (
            end_px[0] / self.scale_px_per_in,
            end_px[1] / self.scale_px_per_in,
        )
        return WallElement(
            start_point=start_in,
            end_point=end_in,
            thickness=self.default_thickness_in,
            layer=self.default_layer,
        )
