"""Unit tests for ``app.core.raster_takeoff.run_raster_takeoff_with_catalog``.

Uses MagicMock RasterParser and a FakeReader for OCR so the full chain
can be exercised without DB, easyocr, or torch.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.core.catalog.catalog_builder import Catalog, CatalogNode
from app.core.catalog.validation_summary import ValidationSummary
from app.core.cv.dimension_extractor import TextBox
from app.core.parsers.raster_parser import RasterParseError
from app.core.raster_takeoff import (
    RasterTakeoffResult,
    _catalog_path_for,
    run_raster_takeoff_with_catalog,
)


class FakeReader:
    """OcrReader satisfying the Sprint 4a Protocol."""

    def __init__(self, text_boxes=None):
        self._text_boxes = list(text_boxes or [])

    def readtext(self, image):
        return self._text_boxes


def _wall_node(id_="wall_0", validation=None) -> CatalogNode:
    return CatalogNode(
        id=id_,
        kind="wall",
        bbox_px=(0, 0, 100, 10),
        length_in=10.0,
        length_source="geometric",
        ocr_validation=validation,
    )


def _make_parser(
    *,
    image=None,
    load_returns=True,
    extract_walls_returns=None,
    extract_walls_raises=None,
):
    """Build a MagicMock RasterParser with the requested behavior."""
    img = image if image is not None else np.zeros((10, 10), dtype=np.uint8)

    parser = MagicMock()
    parser.image = img
    parser.file_path = "/tmp/x.png"
    parser.load = MagicMock(return_value=load_returns)

    if extract_walls_raises is not None:
        parser.extract_walls = MagicMock(side_effect=extract_walls_raises)
    elif extract_walls_returns is not None:
        parser.extract_walls = MagicMock(return_value=extract_walls_returns)
    else:
        parser.extract_walls = MagicMock(return_value=([], {}, None))
    return parser


class TestPathHelper:
    def test_catalog_path_for_under_upload_dir(self, tmp_path):
        path = _catalog_path_for(tmp_path, 42)
        assert path == tmp_path / "analysis" / "42" / "catalog.json"


class TestLoadFlow:
    def test_helper_loads_when_parser_image_is_none(self, tmp_path):
        # If image is None, helper must call .load(); we simulate that
        # by giving the parser image=None at construction and load
        # returning True.
        parser = _make_parser(load_returns=True)
        parser.image = None  # force the load path
        # After load(), the parser's image attribute must be set for the
        # extractor to consume — wire that into the mock side effect.
        def _load_side_effect():
            parser.image = np.zeros((10, 10), dtype=np.uint8)
            return True
        parser.load = MagicMock(side_effect=_load_side_effect)
        parser.extract_walls = MagicMock(return_value=([], {}, None))

        result = run_raster_takeoff_with_catalog(
            parser,
            ocr_reader=FakeReader(),
            takeoff_id=1,
            upload_dir=tmp_path,
        )
        assert parser.load.called
        assert result.summary is None

    def test_helper_raises_when_load_fails(self, tmp_path):
        parser = _make_parser(load_returns=False)
        parser.image = None
        with pytest.raises(RasterParseError, match="Could not load"):
            run_raster_takeoff_with_catalog(
                parser,
                ocr_reader=FakeReader(),
                takeoff_id=1,
                upload_dir=tmp_path,
            )

    def test_helper_skips_load_when_image_already_present(self, tmp_path):
        parser = _make_parser()
        # image is preloaded → no load() call expected
        run_raster_takeoff_with_catalog(
            parser, ocr_reader=FakeReader(), takeoff_id=1, upload_dir=tmp_path
        )
        assert not parser.load.called


class TestScaleWarningPath:
    def test_no_catalog_no_persistence(self, tmp_path):
        # extract_walls returns (walls=[], meta={scale_warning}, catalog=None)
        parser = _make_parser(
            extract_walls_returns=([], {"scale_warning": "need scale"}, None)
        )
        result = run_raster_takeoff_with_catalog(
            parser,
            ocr_reader=FakeReader(),
            takeoff_id=99,
            upload_dir=tmp_path,
        )
        assert result.summary is None
        assert result.catalog_path is None
        assert result.metadata == {"scale_warning": "need scale"}
        # No file written
        assert not (tmp_path / "analysis" / "99" / "catalog.json").exists()


class TestHappyPath:
    def test_catalog_persisted_and_summary_computed(self, tmp_path):
        cat = Catalog(nodes={"wall_0": _wall_node(validation="confirmed")})
        parser = _make_parser(extract_walls_returns=([], {}, cat))

        result = run_raster_takeoff_with_catalog(
            parser,
            ocr_reader=FakeReader(),
            takeoff_id=42,
            upload_dir=tmp_path,
        )
        # Persisted at canonical path
        path = tmp_path / "analysis" / "42" / "catalog.json"
        assert path.exists()
        # Summary populated
        assert isinstance(result.summary, ValidationSummary)
        assert result.summary.walls_confirmed == 1
        assert result.catalog_path == str(path)
        # File is the JSON form of the catalog
        payload = json.loads(path.read_text())
        assert "wall_0" in payload["nodes"]

    def test_walls_passed_through(self, tmp_path):
        walls = ["wall-element-0", "wall-element-1"]  # opaque marker objects
        parser = _make_parser(extract_walls_returns=(walls, {}, Catalog()))
        result = run_raster_takeoff_with_catalog(
            parser, ocr_reader=FakeReader(), takeoff_id=1, upload_dir=tmp_path
        )
        assert result.walls == walls

    def test_returns_frozen_result(self, tmp_path):
        parser = _make_parser(extract_walls_returns=([], {}, Catalog()))
        result = run_raster_takeoff_with_catalog(
            parser, ocr_reader=FakeReader(), takeoff_id=1, upload_dir=tmp_path
        )
        assert isinstance(result, RasterTakeoffResult)
        with pytest.raises(AttributeError):
            result.walls = []  # type: ignore[misc]


class TestOcrThreadsThroughDimensionExtractor:
    def test_dimensions_from_ocr_reach_extract_walls(self, tmp_path):
        # Reader returns one parseable + one non-parseable text box.
        reader = FakeReader(
            [
                TextBox(text='12\'-6"', bbox=(0, 0, 50, 20), confidence=0.95),
                TextBox(text="KITCHEN", bbox=(100, 100, 200, 120), confidence=0.88),
            ]
        )
        parser = _make_parser(extract_walls_returns=([], {}, Catalog()))
        run_raster_takeoff_with_catalog(
            parser, ocr_reader=reader, takeoff_id=1, upload_dir=tmp_path
        )
        # extract_walls received the parsed dimensions; check via call_args
        kwargs = parser.extract_walls.call_args.kwargs
        dims = kwargs["dimensions"]
        assert len(dims) == 1
        assert dims[0].inches == pytest.approx(150.0)


class TestParameterForwarding:
    def test_manual_scale_and_reference_threaded(self, tmp_path):
        parser = _make_parser(extract_walls_returns=([], {}, None))
        run_raster_takeoff_with_catalog(
            parser,
            ocr_reader=FakeReader(),
            takeoff_id=1,
            upload_dir=tmp_path,
            manual_scale='1/4"=1\'-0"',
            reference_measurement={"wall_index": 0, "length_inches": 100},
        )
        kwargs = parser.extract_walls.call_args.kwargs
        assert kwargs["manual_scale"] == '1/4"=1\'-0"'
        assert kwargs["reference_measurement"] == {"wall_index": 0, "length_inches": 100}

    def test_custom_catalog_builder_used(self, tmp_path):
        # Provide a fake builder so we can verify the helper passes it
        # through to extract_walls.
        from app.core.catalog.catalog_builder import ObjectCatalogBuilder

        my_builder = ObjectCatalogBuilder()
        parser = _make_parser(extract_walls_returns=([], {}, None))
        run_raster_takeoff_with_catalog(
            parser,
            ocr_reader=FakeReader(),
            takeoff_id=1,
            upload_dir=tmp_path,
            catalog_builder=my_builder,
        )
        kwargs = parser.extract_walls.call_args.kwargs
        assert kwargs["catalog_builder"] is my_builder
