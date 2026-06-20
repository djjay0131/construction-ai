# Sprint 4e: Scanned-PDF Dispatch (Multi-Page, Page-Tagged)

**Status:** VERIFIED
**Date:** 2026-06-19
**Implemented:** 2026-06-19
**Verified:** 2026-06-20
**Author:** Jason Cusati (with AI assistance)
**Sprint:** 4e of 5 (interstitial — needed before Sprint 5 e2e harness)
**Depends on:** Sprint 4d VERIFIED.

## Problem

A scanned-PDF upload (PDF where each page is an embedded raster image
rather than vector paths — typical of historical drawings, phone scans,
or print-then-scan workflows) currently produces a takeoff with zero
walls. The PDF branch in `app/api/takeoff.py` calls PyMuPDF vector
extraction (`pdf_parser.extract_walls`), which finds nothing in raster
content; the raster pipeline never runs because the file format is
`pdf`, not `jpg/png`.

This blocks Sprint 5: the Phase 1 e2e harness requires three plan
paths exercised end-to-end (DXF + vector PDF + scanned PDF), and the
scanned-PDF path has no code today.

Real-world plan sets often span multiple pages where each page is a
different floor of the building. Page-level provenance must survive
into the catalog so downstream consumers can attribute walls and
objects to a floor.

## Goals

- New `app/core/pdf_takeoff.py` module with
  `run_pdf_takeoff(file_path, *, takeoff_id, upload_dir, ocr_reader,
  line_extractor_factory, dpi, manual_scale=None) -> PdfTakeoffResult`.
- **Per-page dispatch (strict zero)**: for each page, try PyMuPDF
  vector extraction first; if `len(walls) == 0`, rasterize that page
  at the configured DPI and run the Sprint 4d raster pipeline. No
  hybrid mode — a page is either vector or raster, never both.
- Every wall tagged with `metadata["page"]` (0-indexed) and
  `metadata["source"]` (`"pdf_vector"` or `"pdf_raster"`) regardless
  of dispatch path.
- Single merged catalog with page-prefixed node IDs
  (`page_0/wall_0`, `page_1/wall_3`) persisted at the canonical Sprint
  4d path `{upload_dir}/analysis/{takeoff_id}/catalog.json`.
- `app/api/takeoff.py` PDF branch refactored to call `run_pdf_takeoff`;
  takeoff response shape unchanged.
- New `settings.PDF_RASTERIZE_DPI` (default 300, uncapped per user
  direction — caller can set arbitrarily high).
- ≥80% line coverage on the new module; zero regression in the 259
  Sprint 2/3/4 tests.

## Non-Goals

- **Hybrid vector+raster on the same page** — explicitly cut during
  spec review. If real Sprint 5 fixtures expose pages that benefit
  from hybrid extraction, hybrid + dedup becomes a follow-up sprint
  with evidence behind it.
- **Dedup of overlapping walls across pipelines** — cut with hybrid.
  N/A under strict-zero dispatch.
- **PDF unit-scaling fix** — `PDFWallElement.length_inches` treats
  PDF points as inches, which is only correct for 1:1-scale PDFs.
  Tracked as Sprint 4f / backlog item; not in scope here.
- **End-to-end smoke against a real deployed scanned PDF** — handled
  in Sprint 5 with the user-provided fixtures.
- **Detecting individual floors as semantic units** — page = floor is
  a convention surfaced via `metadata["page"]`. Naming pages "Floor 1"
  vs "Basement" is downstream UI work.
- **Top-level warning surfacing of failed pages** — page-level
  raster failures are tagged in `metadata["per_page_sources"]` only.
  If operators need a louder signal, that's a follow-up.
- **Multi-page catalog enumeration in the catalog API** — single
  merged catalog preserves the Sprint 4c contract; per-page
  traversal is a frontend concern (`node.id.split("/")[0]`).
- **Memory caps / DPI clamping** — user explicitly opted for "as high
  as we need." The setting carries a sensible default; abuse is the
  caller's choice.

## User Stories

- **As a takeoff operator**, I want to upload a scanned PDF plan set
  and get a takeoff with walls + catalog, so that I can use historical
  drawings without re-digitizing them.
- **As a frontend developer**, I want each wall and catalog node
  tagged with its source page, so that I can present floor-level
  breakdowns of the takeoff.
- **As a vector-PDF user**, I want my existing workflow unchanged, so
  that the new scanned-PDF support doesn't regress my use case.

## Design Approach

### Architecture

```
takeoff.py PDF branch
    │
    └─→ pdf_takeoff.run_pdf_takeoff()
            │
            ├─→ PDFParser.load()  (PyMuPDF document)
            │
            ├─ for each page p:
            │     │
            │     ├─→ vec_walls = pdf_parser.extract_walls([p])
            │     │
            │     ├─ if vec_walls:                  # vector page
            │     │     all_walls.extend(vec_walls tagged page=p, source=pdf_vector)
            │     │
            │     └─ else:                          # scanned page (strict zero)
            │           img = _rasterize_page(p, dpi)
            │           rp = RasterParser(..., image_loader=lambda: img)
            │           result = run_raster_takeoff_with_catalog(rp, ...)
            │           all_walls.extend(result.walls tagged page=p, source=pdf_raster)
            │           merged_catalog[f"page_{p}/{id}"] = node  for each catalog node
            │
            └─→ CatalogStore.save(merged_catalog, canonical_path)
```

### Why strict-zero threshold

Spec review surfaced trade-offs:

- Strict-zero (`== 0` → raster): vector PDFs with stray artifacts
  (e.g., a single border line) produce a bogus 1-wall takeoff. Rare
  in practice; recoverable by re-uploading.
- Threshold > 0 (`< 3` → raster): catches stray-artifact case but
  introduces a gray zone (1-2 vector walls), which only resolves
  cleanly via hybrid extraction + dedup — both explicitly cut for
  scope.

Strict-zero is the simplest dispatch that satisfies the original ask:
"get scanned PDFs through the pipeline so Sprint 5 can exercise that
path." Sprint 5's real fixtures will tell us if the gray zone matters.

### Why a new module instead of extending `raster_takeoff.py`

`raster_takeoff.py` is single-bitmap-in, single-catalog-out.
`pdf_takeoff.py` orchestrates a loop over pages, each of which is
either a vector parse or a raster pipeline invocation. Keeping them
separate matches the existing parser-per-format split
(`dxf_parser.py`, `pdf_parser.py`, `raster_parser.py`).

### Per-page sources reported in metadata

`metadata["per_page_sources"]: dict[int, str]` enumerates how each
page was processed:
- `"vector"` — vector extraction returned ≥1 walls
- `"raster"` — strict-zero triggered, raster fallback succeeded
- `"raster_failed"` — strict-zero triggered, raster fallback raised
  `RasterParseError`. That page contributes nothing; the takeoff
  still succeeds with whatever other pages produced.

### `WallLineExtractor` factory, `OcrReader` instance

`WallLineExtractor` is instantiated *per-scanned-page* via the
`line_extractor_factory` callable because Sprint 4d's
`last_detections` cache lives on the extractor instance — reusing the
same extractor across pages would leak the previous page's YOLO
detections into the next page's catalog. The factory is cheap (wraps
a singleton-loaded YOLO model via `get_detection_service()`).

`OcrReader` is passed in as a single instance because EasyOcrReader
has no per-page state to leak and constructing it is expensive
(loads easyocr models). The route layer constructs one and threads
it through.

### `image_loader` injection

`RasterParser.__init__` already accepts an `image_loader` for testing.
Sprint 4e reuses that hook in production: the rasterized PDF page is a
`numpy.ndarray` in memory, so we inject a closure
`lambda _p, _img=arr: _img`. This avoids the round-trip-through-disk
that `cv2.imread` would force.

### Catalog merge strategy

Each scanned page's raster pipeline writes its own intermediate
catalog under `analysis/{takeoff_id}/catalog.json` (the Sprint 4d
helper does this unconditionally). Sprint 4e:

1. Loads each intermediate via `CatalogStore.load`
2. Re-keys nodes by `f"page_{p}/{node_id}"` into a `Catalog`
   accumulator
3. At the end, overwrites `analysis/{takeoff_id}/catalog.json` with
   the merged catalog

Trade-off: small write amplification (the last page's intermediate
catalog gets clobbered by the merged write). Reuses Sprint 4d
unchanged, which is the higher-leverage win.

### Settings change

`backend/app/core/config.py`:
```python
class Settings(BaseSettings):
    ...
    PDF_RASTERIZE_DPI: int = 300
```

The takeoff API passes `_settings.PDF_RASTERIZE_DPI` to
`run_pdf_takeoff`. Tests parametrize via the function arg.

## Sample Implementation

```python
# backend/app/core/pdf_takeoff.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import logging
import cv2
import fitz
import numpy as np

from app.core.catalog.catalog_builder import Catalog, ObjectCatalogBuilder
from app.core.catalog.catalog_store import CatalogStore
from app.core.catalog.validation_summary import (
    ValidationSummary, summarise_validation,
)
from app.core.parsers.dxf_parser import WallElement
from app.core.parsers.pdf_parser import PDFParser
from app.core.parsers.raster_parser import RasterParser, RasterParseError
from app.core.raster_takeoff import run_raster_takeoff_with_catalog

if TYPE_CHECKING:  # pragma: no cover
    from app.core.cv.dimension_extractor import OcrReader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PdfTakeoffResult:
    walls: list                # list[WallElement]
    metadata: dict             # per_page_sources, page_count
    summary: Optional[ValidationSummary]
    catalog_path: Optional[str]


def _rasterize_page(page: fitz.Page, dpi: int) -> np.ndarray:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3,
    )
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _vector_walls_for_page(pdf, page_idx):
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
    line_extractor_factory,
    dpi: int,
    manual_scale: Optional[str] = None,
) -> PdfTakeoffResult:
    pdf = PDFParser(file_path)
    if not pdf.load():
        raise RuntimeError(f"Failed to load PDF {file_path}")

    all_walls: list[WallElement] = []
    merged_catalog = Catalog()
    per_page_sources: dict[int, str] = {}

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
            logger.warning("Page %d raster fallback failed: %s", idx, exc)
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

    pdf.close()

    final_path = Path(upload_dir) / "analysis" / str(takeoff_id) / "catalog.json"
    summary = None
    if merged_catalog.nodes:
        CatalogStore().save(merged_catalog, final_path)
        summary = summarise_validation(merged_catalog)

    return PdfTakeoffResult(
        walls=all_walls,
        metadata={
            "per_page_sources": per_page_sources,
            "page_count": len(pdf.doc),
        },
        summary=summary,
        catalog_path=str(final_path) if summary else None,
    )
```

### `app/api/takeoff.py` PDF branch (final shape)

```python
elif drawing.file_format.value == 'pdf':
    from app.core.cv.detection_service import get_detection_service
    from app.core.cv.easyocr_reader import EasyOcrReader
    from app.core.cv.wall_line_extractor import WallLineExtractor
    from app.core.pdf_takeoff import run_pdf_takeoff
    from app.core.config import settings as _settings

    try:
        result = run_pdf_takeoff(
            drawing.file_path,
            takeoff_id=takeoff_record.id,
            upload_dir=_settings.UPLOAD_DIR,
            ocr_reader=EasyOcrReader(),
            line_extractor_factory=lambda: WallLineExtractor(
                detector=get_detection_service(),
            ),
            dpi=_settings.PDF_RASTERIZE_DPI,
            manual_scale=manual_scale,
        )
    except RuntimeError as exc:
        raise Exception(str(exc)) from exc

    walls = result.walls
    if result.summary is not None:
        catalog_note = (
            f"\nPDF catalog: {result.summary} "
            f"(saved to {result.catalog_path})"
        )
        takeoff_record.notes = (takeoff_record.notes or "") + catalog_note
    logger.info(
        "PDF takeoff: %d pages, per_page_sources=%s",
        result.metadata["page_count"],
        result.metadata["per_page_sources"],
    )
```

## Edge Cases & Error Handling

### Page with vector walls
- **Scenario**: `pdf_parser.extract_walls([p])` returns ≥1 wall
- **Behavior**: vector walls extended into result with
  `source="pdf_vector"`, `page=p`. No rasterization, no catalog
  contribution.
- **Test**: AC-2

### Page with zero vector walls
- **Scenario**: `pdf_parser.extract_walls([p])` returns []
- **Behavior**: rasterize page at configured DPI, run raster
  pipeline, walls tagged `source="pdf_raster"`, catalog nodes merged
  with `page_{p}/` prefix.
- **Test**: AC-3

### Page-level raster failure
- **Scenario**: scanned page where `run_raster_takeoff_with_catalog`
  raises `RasterParseError` (no scale detectable, skew rejection)
- **Behavior**: log warning, mark
  `per_page_sources[p]="raster_failed"`, continue. Takeoff succeeds
  with whatever other pages produced.
- **Test**: AC-6

### Mixed vector/scanned pages
- **Scenario**: multi-page PDF where some pages are vector (CAD-export
  of one floor) and others are scanned
- **Behavior**: each page dispatched independently; walls tagged by
  source. `per_page_sources` records every page's path.
- **Test**: AC-4

### Catalog ID collision across pages
- **Scenario**: page 0 catalog has nodes `wall_0, wall_1`; page 1
  also has `wall_0, wall_1`
- **Behavior**: merged catalog has 4 nodes:
  `page_0/wall_0, page_0/wall_1, page_1/wall_0, page_1/wall_1`.
- **Test**: AC-5

### Empty PDF (zero pages)
- **Scenario**: PDF with 0 pages
- **Behavior**: empty walls, no catalog, `page_count: 0`. No crash.
- **Test**: AC-7

### PDFParser.load() returns False
- **Scenario**: corrupted PDF or non-PDF file with `.pdf` extension
- **Behavior**: raise `RuntimeError` with file path in message.
- **Test**: AC-8

### All pages all-scanned all-fail
- **Scenario**: every page hits `raster_failed`
- **Behavior**: empty walls, no catalog, `per_page_sources` all
  `"raster_failed"`. Takeoff response carries 0 walls.
- **Test**: covered by AC-6 generalization

## Acceptance Criteria

### AC-1: `_rasterize_page` returns a BGR ndarray
- **Given** a real PyMuPDF page constructed in-memory
- **When** `_rasterize_page(page, dpi=300)` is called
- **Then** result is a `numpy.ndarray` with `shape == (H, W, 3)` and
  `dtype == np.uint8`

### AC-2: Vector page uses vector extraction
- **Given** a single-page PDF whose vector extraction returns ≥1 walls
- **When** `run_pdf_takeoff` runs
- **Then** all vector walls appear in `result.walls` tagged
  `source="pdf_vector"` and `page=0`
- **And** `per_page_sources[0] == "vector"`
- **And** rasterization is not called for that page

### AC-3: Page with 0 vector walls triggers raster fallback
- **Given** a single-page PDF where vector extraction returns 0 walls
  and the raster pipeline returns N walls + a catalog
- **When** `run_pdf_takeoff` runs
- **Then** `result.walls` has N entries tagged
  `source="pdf_raster"` and `page=0`
- **And** `per_page_sources[0] == "raster"`
- **And** the merged catalog has the raster pipeline's nodes re-keyed
  under `page_0/...`

### AC-4: Mixed pages handled independently
- **Given** a 3-page PDF where page 0 has vector walls, pages 1-2
  have 0 vector walls but raster pipeline produces walls each
- **When** `run_pdf_takeoff` runs
- **Then** page 0 walls have `source="pdf_vector"`, pages 1-2 walls
  have `source="pdf_raster"`, all pages contribute to `result.walls`,
  `per_page_sources == {0:"vector", 1:"raster", 2:"raster"}`

### AC-5: Catalog merge uses page-prefixed IDs
- **Given** a 2-page PDF where both pages go through the raster
  pipeline and each page's catalog has 2 nodes (`wall_0`, `wall_1`)
- **When** `run_pdf_takeoff` runs
- **Then** the persisted catalog at
  `{upload_dir}/analysis/{takeoff_id}/catalog.json` has 4 nodes with
  IDs `page_0/wall_0`, `page_0/wall_1`, `page_1/wall_0`,
  `page_1/wall_1`

### AC-6: Page-level raster failure doesn't break the takeoff
- **Given** a 2-page PDF where page 0 vector returns 0 walls (raster
  fallback succeeds with 2 walls) and page 1's raster pipeline raises
  `RasterParseError`
- **When** `run_pdf_takeoff` runs
- **Then** `result.walls` has 2 entries (from page 0);
  `per_page_sources == {0:"raster", 1:"raster_failed"}`;
  `result.summary` reflects page 0's catalog; no crash

### AC-7: Empty PDF returns empty result
- **Given** a 0-page PDF document
- **When** `run_pdf_takeoff` runs
- **Then** `result.walls == []`; `result.catalog_path is None`;
  `result.metadata["page_count"] == 0`; no crash

### AC-8: PDFParser.load() failure surfaces as RuntimeError
- **Given** a `PDFParser` whose `.load()` returns False
- **When** `run_pdf_takeoff` runs
- **Then** `RuntimeError` is raised with the file path in the message

### AC-9: Per-page line-extractor isolation
- **Given** a 2-page PDF where both pages need raster fallback
- **When** `run_pdf_takeoff` runs
- **Then** `line_extractor_factory()` is called twice (once per
  scanned page), ensuring `WallLineExtractor.last_detections` doesn't
  leak across pages

### AC-10: ≥80% coverage + regression + ruff clean
- **Given** the implementation is complete
- **When** the new tests run with coverage
- **Then** `app.core.pdf_takeoff` has ≥80% line coverage
- **And** the 259 prior Sprint 2/3/4 tests still pass
- **And** ruff is clean on the new module and modified files

## Technical Notes

- **Affected files:**
  - `backend/app/core/pdf_takeoff.py` (new, ~80 stmts est.)
  - `backend/app/core/config.py` (add `PDF_RASTERIZE_DPI: int = 300`)
  - `backend/app/api/takeoff.py` (refactor PDF branch to call helper)
  - `backend/tests/test_pdf_takeoff.py` (new, ~15 tests est.)
  - `.github/workflows/ci.yml` (add test file + `--cov=app.core.pdf_takeoff`)

- **Test strategy:** Build small synthetic PDFs in-memory via PyMuPDF
  (`fitz.open()` + `doc.new_page()`). Mock `PDFParser.extract_walls`
  to return controlled wall counts per page. Mock the raster pipeline
  via `monkeypatch` on `run_raster_takeoff_with_catalog` so we don't
  load torch/easyocr in unit tests. AC-1 is the only test that
  exercises a real PyMuPDF rasterization path.

- **Dependencies:** PyMuPDF (`fitz`) already in `requirements.txt`
  per Sprint 3a wiring. No new packages.

- **Patterns to follow:** Mirror `raster_takeoff.py` — frozen result
  dataclass, helper-orchestrates / API-stays-thin, RuntimeError on
  load failure with caller-responsible wrapping.

## Dependencies

- Sprint 4d VERIFIED. (Done.)
- PyMuPDF ≥ 1.23. (Already in deps.)

## Open Questions

- **Hybrid vector+raster + dedup** — cut from this sprint. If Sprint
  5 fixtures expose pages where strict-zero misclassifies, hybrid +
  pixel-coord dedup becomes its own follow-up sprint with evidence.
- **PDF vector-parser unit-scaling fix** — separate sprint (4f /
  backlog). `PDFWallElement.length_inches` is only correct for
  1:1-scale PDFs; real construction PDFs at `1/4"=1'-0"` produce
  wrong wall lengths today. Not blocking 4e or Sprint 5.
- **Top-level warning surfacing of `raster_failed` pages** — cut.
  Page-level failures live in `metadata["per_page_sources"]`. Revisit
  if operators report missing the signal.
