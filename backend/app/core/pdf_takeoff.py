"""Multi-page PDF takeoff: per-page vector OR raster dispatch.

For each page in the PDF, try PyMuPDF vector extraction first. If any
walls are found, keep them tagged ``source="pdf_vector"``. If the
page yields zero vector walls (strict-zero threshold), rasterize that
page at the configured DPI and run the Sprint 4d raster pipeline,
tagging its walls ``source="pdf_raster"``. Walls aggregate across
pages; the catalog merges with page-prefixed IDs
(``page_0/wall_0`` etc.) so the same node ID emitted by independent
per-page raster runs never collides.

The dispatch model treats each page independently — a mixed
vector/scanned PDF (page 0 CAD-export, pages 1-2 phone scan) handles
both branches in one run. Page-level raster failures are logged and
tagged ``"raster_failed"`` in ``metadata["per_page_sources"]``; the
takeoff still succeeds with whatever other pages produced.

Hybrid in-page extraction (union vector + raster on the same page)
and dedup are explicitly out of scope here — see the spec's Open
Questions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

import cv2
import fitz
import numpy as np

from app.core.catalog.catalog_builder import Catalog, ObjectCatalogBuilder
from app.core.catalog.catalog_store import CatalogStore
from app.core.catalog.validation_summary import (
    ValidationSummary,
    summarise_validation,
)
from app.core.parsers.dxf_parser import WallElement
from app.core.parsers.pdf_parser import PDFParser
from app.core.parsers.raster_parser import RasterParser, RasterParseError
from app.core.raster_takeoff import run_raster_takeoff_with_catalog

if TYPE_CHECKING:  # pragma: no cover - lazy import to keep tests light
    from app.core.cv.dimension_extractor import OcrReader
    from app.core.cv.wall_line_extractor import WallLineExtractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfTakeoffResult:
    """Bundle returned by :func:`run_pdf_takeoff`.

    ``summary`` and ``catalog_path`` are populated only when at least
    one page produced a non-empty catalog (merged across all scanned
    pages). ``metadata`` always carries ``per_page_sources`` (dict
    keyed by page index) and ``page_count``.
    """

    walls: list  # list[WallElement] aggregated across pages, page-tagged
    metadata: dict
    summary: Optional[ValidationSummary]
    catalog_path: Optional[str]


def _rasterize_page(page: fitz.Page, dpi: int) -> np.ndarray:
    """Render ``page`` to a BGR ndarray that ``RasterParser`` can consume."""
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3,
    )
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _vector_walls_for_page(pdf: PDFParser, page_idx: int) -> list[WallElement]:
    """Convert PDFParser vector walls for one page into tagged WallElements."""
    pdf_walls = pdf.extract_walls(page_numbers=[page_idx])
    return [
        WallElement(
            start_point=w.start_point,
            end_point=w.end_point,
            layer=f"page_{w.page_number}",
            metadata={
                "source": "pdf_vector",
                "page": w.page_number,
                **w.metadata,
            },
        )
        for w in pdf_walls
    ]


def run_pdf_takeoff(
    file_path,
    *,
    takeoff_id: int,
    upload_dir,
    ocr_reader: "OcrReader",
    line_extractor_factory: "Callable[[], WallLineExtractor]",
    dpi: int,
    manual_scale: Optional[str] = None,
) -> PdfTakeoffResult:
    """Run vector-first / raster-fallback dispatch across every page.

    The OCR reader is shared across pages (no per-page state to leak);
    ``line_extractor_factory`` is invoked once per scanned page because
    :attr:`WallLineExtractor.last_detections` would otherwise leak
    YOLO output across pages and contaminate downstream catalogs.

    Raises :class:`RuntimeError` if the PDF cannot be loaded.
    """
    pdf = PDFParser(file_path, manual_scale=manual_scale)
    if not pdf.load():
        raise RuntimeError(f"Failed to load PDF {file_path}")

    all_walls: list[WallElement] = []
    merged_catalog = Catalog()
    per_page_sources: dict[int, str] = {}

    try:
        for idx, page in enumerate(pdf.doc):
            vec_walls = _vector_walls_for_page(pdf, idx)
            if vec_walls:
                all_walls.extend(vec_walls)
                per_page_sources[idx] = "vector"
                continue

            img = _rasterize_page(page, dpi)
            rp = RasterParser(
                file_path,
                line_extractor=line_extractor_factory(),
                image_loader=lambda _p, _img=img: _img,
            )
            rp.load()
            try:
                result = run_raster_takeoff_with_catalog(
                    rp,
                    ocr_reader=ocr_reader,
                    takeoff_id=takeoff_id,
                    upload_dir=upload_dir,
                    manual_scale=manual_scale,
                    catalog_builder=ObjectCatalogBuilder(),
                )
            except RasterParseError as exc:
                logger.warning(
                    "Page %d raster fallback failed: %s", idx, exc,
                )
                per_page_sources[idx] = "raster_failed"
                continue

            for w in result.walls:
                w.metadata.update({"source": "pdf_raster", "page": idx})
                all_walls.append(w)

            if result.catalog_path:
                page_cat = CatalogStore().load(Path(result.catalog_path))
                for node_id, node in page_cat.nodes.items():
                    merged_catalog.nodes[f"page_{idx}/{node_id}"] = node
            per_page_sources[idx] = "raster"

        page_count = len(pdf.doc)
    finally:
        pdf.close()

    final_path = Path(upload_dir) / "analysis" / str(takeoff_id) / "catalog.json"
    summary: Optional[ValidationSummary] = None
    if merged_catalog.nodes:
        CatalogStore().save(merged_catalog, final_path)
        summary = summarise_validation(merged_catalog)

    return PdfTakeoffResult(
        walls=all_walls,
        metadata={
            "per_page_sources": per_page_sources,
            "page_count": page_count,
        },
        summary=summary,
        catalog_path=str(final_path) if summary else None,
    )
