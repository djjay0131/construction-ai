"""Unit tests for ``app.core.pdf_takeoff.run_pdf_takeoff``.

Tests use real in-memory PyMuPDF documents (built via ``fitz.open()`` +
``doc.new_page()``) so the page-iteration + rasterization paths run for
real. Vector wall counts per page are controlled by monkeypatching
``_vector_walls_for_page`` at the module level. The raster pipeline is
stubbed via ``run_raster_takeoff_with_catalog`` so we don't load torch
or easyocr in unit tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import fitz
import numpy as np
import pytest

from app.core.catalog.catalog_builder import Catalog, CatalogNode
from app.core.catalog.catalog_store import CatalogStore
from app.core.catalog.validation_summary import summarise_validation
from app.core.parsers.dxf_parser import WallElement
from app.core.parsers.raster_parser import RasterParseError
from app.core.pdf_takeoff import (
    PdfTakeoffResult,
    _rasterize_page,
    _vector_walls_for_page,
    run_pdf_takeoff,
)
from app.core.raster_takeoff import RasterTakeoffResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class FakeReader:
    """Stand-in for the EasyOcrReader Protocol; no per-page state."""

    def readtext(self, image):
        return []


def make_pdf(tmp_path, num_pages, name="test.pdf"):
    """Build a PDF with ``num_pages`` empty (no-drawing) pages."""
    path = tmp_path / name
    doc = fitz.open()
    for _ in range(num_pages):
        doc.new_page(width=612, height=792)
    doc.save(str(path))
    doc.close()
    return str(path)


def _wall(x0=0, y0=0, x1=10, y1=0, page=None, source=None):
    md = {}
    if page is not None:
        md["page"] = page
    if source is not None:
        md["source"] = source
    return WallElement(start_point=(x0, y0), end_point=(x1, y1), metadata=md)


def _catalog_with(nodes):
    """Build a Catalog with (id, kind) tuples."""
    cat = Catalog()
    for nid, kind in nodes:
        cat.nodes[nid] = CatalogNode(
            id=nid,
            kind=kind,
            bbox_px=(0, 0, 100, 10),
            length_in=10.0,
            length_source="geometric",
            ocr_validation="confirmed" if kind == "wall" else None,
        )
    return cat


def make_vector_stub(per_page_walls):
    """Stub for ``_vector_walls_for_page``.

    ``per_page_walls``: dict mapping page idx → list[WallElement]. Pages
    not in the dict return ``[]`` (i.e., trigger raster fallback).
    """
    def _stub(pdf, page_idx):
        walls = per_page_walls.get(page_idx, [])
        # Mirror the production tagging that the real helper applies.
        return [
            WallElement(
                start_point=w.start_point,
                end_point=w.end_point,
                layer=f"page_{page_idx}",
                metadata={"source": "pdf_vector", "page": page_idx, **w.metadata},
            )
            for w in walls
        ]
    return _stub


def make_raster_stub(per_call_results):
    """Stub for ``run_raster_takeoff_with_catalog``.

    Each spec is a dict with optional ``walls``, ``catalog_nodes``,
    and ``raise_``. When ``catalog_nodes`` is set the stub writes a
    real catalog JSON at the canonical Sprint-4d path and returns
    ``catalog_path`` pointing to it.
    """
    state = {"call": 0}

    def _stub(rp, *, ocr_reader, takeoff_id, upload_dir, **kwargs):
        idx = state["call"]
        state["call"] += 1
        spec = per_call_results[idx]
        if "raise_" in spec:
            raise spec["raise_"]
        walls = spec.get("walls", [])
        nodes = spec.get("catalog_nodes")
        if nodes:
            cat = _catalog_with(nodes)
            path = Path(upload_dir) / "analysis" / str(takeoff_id) / "catalog.json"
            CatalogStore().save(cat, path)
            return RasterTakeoffResult(
                walls=walls,
                metadata={},
                summary=summarise_validation(cat),
                catalog_path=str(path),
            )
        return RasterTakeoffResult(
            walls=walls, metadata={}, summary=None, catalog_path=None,
        )

    _stub.state = state
    return _stub


# ---------------------------------------------------------------------------
# AC-1: _rasterize_page returns a BGR ndarray
# ---------------------------------------------------------------------------


class TestRasterizePage:
    def test_returns_bgr_ndarray_with_expected_dtype_and_shape(self):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)  # letter
        arr = _rasterize_page(page, dpi=150)
        doc.close()

        assert isinstance(arr, np.ndarray)
        assert arr.dtype == np.uint8
        assert arr.ndim == 3
        assert arr.shape[2] == 3
        assert arr.shape[1] == int(round(612 * 150 / 72))
        assert arr.shape[0] == int(round(792 * 150 / 72))

    def test_dpi_scales_output_dimensions(self):
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        small = _rasterize_page(page, dpi=72)
        large = _rasterize_page(page, dpi=300)
        doc.close()

        assert small.shape[0] < large.shape[0]
        assert small.shape[1] < large.shape[1]


# ---------------------------------------------------------------------------
# AC-2: Vector page uses vector extraction; raster never invoked
# ---------------------------------------------------------------------------


class TestVectorPage:
    def test_vector_walls_passed_through_with_source_and_page_tags(
        self, tmp_path, monkeypatch,
    ):
        pdf_path = make_pdf(tmp_path, num_pages=1)
        # Page 0 returns 5 vector walls; no other pages.
        vec_stub = make_vector_stub({0: [_wall() for _ in range(5)]})
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", vec_stub,
        )
        raster_stub = make_raster_stub([])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )
        factory = MagicMock(side_effect=lambda: MagicMock())

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=factory,
            dpi=150,
        )

        assert raster_stub.state["call"] == 0
        assert factory.call_count == 0
        assert len(result.walls) == 5
        for w in result.walls:
            assert w.metadata["source"] == "pdf_vector"
            assert w.metadata["page"] == 0
        assert result.metadata["per_page_sources"] == {0: "vector"}
        assert result.metadata["page_count"] == 1


# ---------------------------------------------------------------------------
# AC-3: Page with 0 vector walls triggers raster
# ---------------------------------------------------------------------------


class TestRasterFallback:
    def test_scanned_page_walls_tagged_pdf_raster(self, tmp_path, monkeypatch):
        pdf_path = make_pdf(tmp_path, num_pages=1)
        # Empty vector stub → page 0 returns [], triggers raster.
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", make_vector_stub({}),
        )
        raster_walls = [_wall(0, 0, 100, 0), _wall(0, 50, 100, 50)]
        raster_stub = make_raster_stub([
            {
                "walls": raster_walls,
                "catalog_nodes": [("wall_0", "wall"), ("wall_1", "wall")],
            },
        ])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=7,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        assert raster_stub.state["call"] == 1
        assert len(result.walls) == 2
        for w in result.walls:
            assert w.metadata["source"] == "pdf_raster"
            assert w.metadata["page"] == 0
        assert result.metadata["per_page_sources"] == {0: "raster"}


# ---------------------------------------------------------------------------
# AC-4: Mixed pages handled independently
# ---------------------------------------------------------------------------


class TestMixedPages:
    def test_per_page_sources_records_each_path(self, tmp_path, monkeypatch):
        pdf_path = make_pdf(tmp_path, num_pages=3)
        # Page 0 has vector walls; pages 1+2 don't.
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page",
            make_vector_stub({0: [_wall(), _wall()]}),
        )
        raster_stub = make_raster_stub([
            {
                "walls": [_wall(0, 0, 50, 0)],
                "catalog_nodes": [("wall_0", "wall")],
            },
            {
                "walls": [_wall(0, 0, 60, 0)],
                "catalog_nodes": [("wall_0", "wall")],
            },
        ])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=2,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        # Vector walls from page 0 + 1 raster wall from each of pages 1+2.
        assert len(result.walls) == 4
        sources_by_page = {}
        for w in result.walls:
            sources_by_page.setdefault(w.metadata["page"], set()).add(
                w.metadata["source"],
            )
        assert sources_by_page[0] == {"pdf_vector"}
        assert sources_by_page[1] == {"pdf_raster"}
        assert sources_by_page[2] == {"pdf_raster"}
        assert result.metadata["per_page_sources"] == {
            0: "vector", 1: "raster", 2: "raster",
        }
        assert result.metadata["page_count"] == 3


# ---------------------------------------------------------------------------
# AC-5: Catalog merge uses page-prefixed IDs
# ---------------------------------------------------------------------------


class TestCatalogMerge:
    def test_node_ids_prefixed_by_page(self, tmp_path, monkeypatch):
        pdf_path = make_pdf(tmp_path, num_pages=2)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", make_vector_stub({}),
        )
        raster_stub = make_raster_stub([
            {
                "walls": [_wall()],
                "catalog_nodes": [("wall_0", "wall"), ("wall_1", "wall")],
            },
            {
                "walls": [_wall()],
                "catalog_nodes": [("wall_0", "wall"), ("wall_1", "wall")],
            },
        ])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=42,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        final_path = tmp_path / "analysis" / "42" / "catalog.json"
        assert result.catalog_path == str(final_path)
        merged = CatalogStore().load(final_path)
        assert set(merged.nodes) == {
            "page_0/wall_0", "page_0/wall_1",
            "page_1/wall_0", "page_1/wall_1",
        }
        assert result.summary is not None
        assert result.summary.walls_total == 4


# ---------------------------------------------------------------------------
# AC-6: Page-level raster failure doesn't break the takeoff
# ---------------------------------------------------------------------------


class TestRasterFailureResilience:
    def test_one_page_fails_others_succeed(self, tmp_path, monkeypatch):
        pdf_path = make_pdf(tmp_path, num_pages=2)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", make_vector_stub({}),
        )
        raster_stub = make_raster_stub([
            {
                "walls": [_wall(0, 0, 100, 0), _wall(0, 50, 100, 50)],
                "catalog_nodes": [("wall_0", "wall")],
            },
            {"raise_": RasterParseError("no scale detectable")},
        ])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=9,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        assert len(result.walls) == 2
        assert result.metadata["per_page_sources"] == {
            0: "raster", 1: "raster_failed",
        }
        assert result.summary is not None
        assert result.catalog_path is not None


# ---------------------------------------------------------------------------
# AC-7: Empty PDF returns empty result
# ---------------------------------------------------------------------------


class TestEmptyPdf:
    def test_zero_page_pdf_returns_empty_result(self, tmp_path, monkeypatch):
        # PyMuPDF refuses to save a 0-page PDF; fake the load to return a
        # 0-length doc instead. This still exercises the dispatcher's
        # zero-page branch.
        from app.core.parsers import pdf_parser as pp

        class FakeDoc:
            def __iter__(self):
                return iter([])

            def __len__(self):
                return 0

        def _fake_load(self):
            self.doc = FakeDoc()
            return True

        monkeypatch.setattr(pp.PDFParser, "load", _fake_load)
        monkeypatch.setattr(pp.PDFParser, "close", lambda self: None)

        result = run_pdf_takeoff(
            "/dev/null",
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        assert result.walls == []
        assert result.catalog_path is None
        assert result.summary is None
        assert result.metadata["page_count"] == 0
        assert result.metadata["per_page_sources"] == {}


# ---------------------------------------------------------------------------
# AC-8: PDFParser.load() failure surfaces as RuntimeError
# ---------------------------------------------------------------------------


class TestLoadFailure:
    def test_unloadable_pdf_raises_runtime_error(self, tmp_path, monkeypatch):
        from app.core.parsers import pdf_parser as pp

        monkeypatch.setattr(pp.PDFParser, "load", lambda self: False)

        with pytest.raises(RuntimeError) as excinfo:
            run_pdf_takeoff(
                "/nope/missing.pdf",
                takeoff_id=1,
                upload_dir=tmp_path,
                ocr_reader=FakeReader(),
                line_extractor_factory=lambda: MagicMock(),
                dpi=150,
            )
        assert "Failed to load PDF" in str(excinfo.value)
        assert "/nope/missing.pdf" in str(excinfo.value)


# ---------------------------------------------------------------------------
# AC-9: Per-page line-extractor isolation
# ---------------------------------------------------------------------------


class TestPerPageIsolation:
    def test_line_extractor_factory_called_once_per_scanned_page(
        self, tmp_path, monkeypatch,
    ):
        pdf_path = make_pdf(tmp_path, num_pages=2)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", make_vector_stub({}),
        )
        raster_stub = make_raster_stub([
            {"walls": []}, {"walls": []},
        ])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )
        factory = MagicMock(side_effect=lambda: MagicMock())

        run_pdf_takeoff(
            pdf_path,
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=factory,
            dpi=150,
        )

        assert factory.call_count == 2

    def test_factory_not_called_when_only_vector_pages(
        self, tmp_path, monkeypatch,
    ):
        pdf_path = make_pdf(tmp_path, num_pages=2)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page",
            make_vector_stub({0: [_wall()], 1: [_wall()]}),
        )
        raster_stub = make_raster_stub([])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )
        factory = MagicMock(side_effect=lambda: MagicMock())

        run_pdf_takeoff(
            pdf_path,
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=factory,
            dpi=150,
        )

        assert factory.call_count == 0


# ---------------------------------------------------------------------------
# Helper coverage: _vector_walls_for_page direct exercise
# ---------------------------------------------------------------------------


class TestVectorWallsForPageHelper:
    def test_returns_empty_list_when_pdfparser_returns_no_walls(
        self, tmp_path, monkeypatch,
    ):
        from app.core.parsers import pdf_parser as pp

        # Real PDFParser, but extract_walls returns [] regardless.
        monkeypatch.setattr(
            pp.PDFParser, "extract_walls", lambda self, page_numbers=None: [],
        )
        path = make_pdf(tmp_path, num_pages=1)
        pdf = pp.PDFParser(path)
        assert pdf.load()
        try:
            walls = _vector_walls_for_page(pdf, 0)
        finally:
            pdf.close()
        assert walls == []

    def test_tags_walls_with_source_and_page_index(
        self, tmp_path, monkeypatch,
    ):
        from app.core.parsers import pdf_parser as pp

        fake_pdf_wall = pp.PDFWallElement(
            start_point=(0, 0),
            end_point=(100, 0),
            page_number=3,
            metadata={"layer": "x"},
        )
        monkeypatch.setattr(
            pp.PDFParser,
            "extract_walls",
            lambda self, page_numbers=None: [fake_pdf_wall],
        )
        path = make_pdf(tmp_path, num_pages=4)
        pdf = pp.PDFParser(path)
        assert pdf.load()
        try:
            walls = _vector_walls_for_page(pdf, 3)
        finally:
            pdf.close()
        assert len(walls) == 1
        w = walls[0]
        assert w.metadata["source"] == "pdf_vector"
        assert w.metadata["page"] == 3
        assert w.metadata["layer"] == "x"
        assert w.layer == "page_3"


# ---------------------------------------------------------------------------
# Misc: dataclass immutability + parameter forwarding
# ---------------------------------------------------------------------------


class TestVectorOnlyHasNoCatalog:
    def test_vector_only_pdf_does_not_persist_a_catalog(
        self, tmp_path, monkeypatch,
    ):
        # Vector walls don't contribute to the catalog (non-goal per spec);
        # if all pages are vector, no catalog file is written.
        pdf_path = make_pdf(tmp_path, num_pages=3)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page",
            make_vector_stub({0: [_wall()], 1: [_wall()], 2: [_wall()]}),
        )
        raster_stub = make_raster_stub([])
        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", raster_stub,
        )

        result = run_pdf_takeoff(
            pdf_path,
            takeoff_id=99,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
        )

        assert result.summary is None
        assert result.catalog_path is None
        # No catalog file written
        assert not (tmp_path / "analysis" / "99" / "catalog.json").exists()
        assert raster_stub.state["call"] == 0


class TestPdfTakeoffResultIsFrozen:
    def test_cannot_mutate_walls_field(self):
        result = PdfTakeoffResult(
            walls=[], metadata={}, summary=None, catalog_path=None,
        )
        with pytest.raises(AttributeError):
            result.walls = []  # type: ignore[misc]


class TestParameterForwarding:
    def test_manual_scale_threaded_to_raster_pipeline(
        self, tmp_path, monkeypatch,
    ):
        pdf_path = make_pdf(tmp_path, num_pages=1)
        monkeypatch.setattr(
            "app.core.pdf_takeoff._vector_walls_for_page", make_vector_stub({}),
        )
        seen = {}

        def _stub(rp, *, ocr_reader, takeoff_id, upload_dir, **kwargs):
            seen.update(kwargs)
            return RasterTakeoffResult(
                walls=[], metadata={}, summary=None, catalog_path=None,
            )

        monkeypatch.setattr(
            "app.core.pdf_takeoff.run_raster_takeoff_with_catalog", _stub,
        )

        run_pdf_takeoff(
            pdf_path,
            takeoff_id=1,
            upload_dir=tmp_path,
            ocr_reader=FakeReader(),
            line_extractor_factory=lambda: MagicMock(),
            dpi=150,
            manual_scale='1/4"=1\'-0"',
        )

        assert seen["manual_scale"] == '1/4"=1\'-0"'
        assert "catalog_builder" in seen
