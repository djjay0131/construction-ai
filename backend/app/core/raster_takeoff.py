"""Raster takeoff orchestration: walls + OCR + catalog + persistence.

Single entry point that the takeoff API calls for JPG/PNG uploads.
Extracted as a helper module so unit tests can exercise the full chain
without touching the takeoff API's DB / file plumbing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from app.core.catalog.catalog_builder import ObjectCatalogBuilder
from app.core.catalog.catalog_store import CatalogStore
from app.core.catalog.validation_summary import (
    ValidationSummary,
    summarise_validation,
)
from app.core.cv.dimension_extractor import DimensionExtractor
from app.core.parsers.raster_parser import RasterParseError, RasterParser

if TYPE_CHECKING:  # pragma: no cover - imports kept lazy at runtime
    from app.core.cv.dimension_extractor import OcrReader
    from app.core.parsers.dxf_parser import WallElement

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RasterTakeoffResult:
    """Bundle returned by :func:`run_raster_takeoff_with_catalog`.

    ``summary`` and ``catalog_path`` are populated only when a catalog
    was successfully built and persisted; otherwise both are ``None``.
    """

    walls: list  # list[WallElement] — kept loose to avoid heavy import in __init__
    metadata: dict
    summary: Optional[ValidationSummary]
    catalog_path: Optional[str]


def _catalog_path_for(upload_dir: str | Path, takeoff_id: int) -> Path:
    return Path(upload_dir) / "analysis" / str(takeoff_id) / "catalog.json"


def run_raster_takeoff_with_catalog(
    raster_parser: RasterParser,
    ocr_reader: "OcrReader",
    *,
    takeoff_id: int,
    upload_dir: str | Path,
    manual_scale: Optional[str] = None,
    reference_measurement: Optional[dict] = None,
    catalog_builder: Optional[ObjectCatalogBuilder] = None,
) -> RasterTakeoffResult:
    """Run the full raster + OCR + catalog pipeline and persist results.

    Returns a :class:`RasterTakeoffResult`. Raises :class:`RasterParseError`
    on non-recoverable failures (image load, skew rejection, no walls).

    ``manual_scale`` and ``reference_measurement`` flow through to
    :meth:`RasterParser.extract_walls`. The catalog is built only when
    ``catalog_builder`` is provided (or defaulted) AND scale detection
    succeeds.
    """
    if raster_parser.image is None and not raster_parser.load():
        raise RasterParseError(f"Could not load image {raster_parser.file_path}")

    builder = catalog_builder or ObjectCatalogBuilder()
    extractor = DimensionExtractor(reader=ocr_reader)
    parsed_dims, _ = extractor.extract(raster_parser.image)

    walls, metadata, catalog = raster_parser.extract_walls(
        manual_scale=manual_scale,
        reference_measurement=reference_measurement,
        catalog_builder=builder,
        dimensions=parsed_dims,
    )

    if catalog is None:
        return RasterTakeoffResult(
            walls=list(walls),
            metadata=metadata,
            summary=None,
            catalog_path=None,
        )

    path = _catalog_path_for(upload_dir, takeoff_id)
    CatalogStore().save(catalog, path)
    summary = summarise_validation(catalog)
    logger.info(
        "Raster takeoff %s: %s; catalog saved to %s",
        takeoff_id,
        summary,
        path,
    )
    return RasterTakeoffResult(
        walls=list(walls),
        metadata=metadata,
        summary=summary,
        catalog_path=str(path),
    )
