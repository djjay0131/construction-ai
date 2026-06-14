"""Unit tests for ``app.core.cv.coordinate_converter``.

Pure-math tests. No images.
"""

from __future__ import annotations

import pytest

from app.core.cv.coordinate_converter import CoordinateConverter
from app.core.parsers.dxf_parser import WallElement


class TestConstructorValidation:
    def test_zero_scale_raises(self):
        with pytest.raises(ValueError, match="positive"):
            CoordinateConverter(scale_px_per_in=0.0)

    def test_negative_scale_raises(self):
        with pytest.raises(ValueError, match="positive"):
            CoordinateConverter(scale_px_per_in=-1.0)

    def test_positive_scale_constructs(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        assert c.scale_px_per_in == 10.0
        assert c.default_thickness_in == 4.0
        assert c.default_layer == "raster"

    def test_kwargs_override_defaults(self):
        c = CoordinateConverter(
            scale_px_per_in=10.0,
            default_thickness_in=6.0,
            default_layer="custom-layer",
        )
        assert c.default_thickness_in == 6.0
        assert c.default_layer == "custom-layer"


class TestToWallElementsHappyPath:
    def test_single_horizontal_segment_produces_correct_wall(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        walls = c.to_wall_elements([((0, 0), (100, 0))])

        assert len(walls) == 1
        wall = walls[0]
        assert isinstance(wall, WallElement)
        assert wall.start_point == (0.0, 0.0)
        assert wall.end_point == (10.0, 0.0)
        assert wall.length_inches == pytest.approx(10.0)
        assert wall.thickness == 4.0
        assert wall.layer == "raster"

    def test_multiple_segments_preserve_order(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        walls = c.to_wall_elements(
            [
                ((0, 0), (100, 0)),
                ((100, 0), (100, 50)),
                ((0, 50), (0, 0)),
            ]
        )
        assert len(walls) == 3
        # Second wall: vertical, 5 inches long
        assert walls[1].length_inches == pytest.approx(5.0)

    def test_fractional_pixel_coordinates(self):
        c = CoordinateConverter(scale_px_per_in=20.0)
        walls = c.to_wall_elements([((0.0, 0.0), (50.5, 0.0))])
        assert walls[0].end_point[0] == pytest.approx(2.525)


class TestToWallElementsEdgeCases:
    def test_empty_input_returns_empty_list(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        assert c.to_wall_elements([]) == []

    def test_diagonal_segment_length(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        # 30, 40, 50 right triangle: hypotenuse should be 5 inches
        walls = c.to_wall_elements([((0, 0), (30, 40))])
        assert walls[0].length_inches == pytest.approx(5.0)

    def test_generator_input(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        # Pass a generator (Iterable, not list) — should still work.
        gen = (((i, 0), (i + 10, 0)) for i in range(3))
        walls = c.to_wall_elements(gen)
        assert len(walls) == 3


class TestPreservesWallElementShape:
    def test_every_item_is_wall_element(self):
        c = CoordinateConverter(scale_px_per_in=10.0)
        walls = c.to_wall_elements([((0, 0), (50, 0)), ((50, 0), (50, 50))])
        for w in walls:
            assert isinstance(w, WallElement)
            assert w.length_inches > 0

    def test_custom_layer_applied_to_every_wall(self):
        c = CoordinateConverter(scale_px_per_in=10.0, default_layer="floor-2")
        walls = c.to_wall_elements([((0, 0), (10, 0)), ((10, 0), (10, 10))])
        assert all(w.layer == "floor-2" for w in walls)
