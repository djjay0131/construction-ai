"""Catalog retrieval endpoint.

``GET /api/catalog/{takeoff_id}`` returns the persisted JSON catalog for
a takeoff. 404 if no catalog file exists for that id.

The takeoff write-path (``app/api/takeoff.py`` raster branch) persists
catalogs under ``{UPLOAD_DIR}/analysis/{takeoff_id}/catalog.json``;
this endpoint reads from the same location.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _catalog_path_for(takeoff_id: int) -> Path:
    """Return the canonical path where a takeoff's catalog should live."""
    return Path(settings.UPLOAD_DIR) / "analysis" / str(takeoff_id) / "catalog.json"


@router.get("/{takeoff_id}")
def get_catalog(takeoff_id: int) -> dict:
    """Return the persisted catalog JSON for a takeoff, or 404."""
    path = _catalog_path_for(takeoff_id)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No catalog found for takeoff_id={takeoff_id}",
        )
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        logger.error("Corrupt catalog at %s: %s", path, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Catalog file at {path} is not valid JSON",
        ) from exc
