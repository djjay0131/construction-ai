"""Unit tests for ``app.api.catalog`` (``GET /api/catalog/{takeoff_id}``).

Mounts only the catalog router on a minimal FastAPI app so tests don't
load the full backend dependency graph (cv2, torch, ultralytics, ...).
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Point ``settings.UPLOAD_DIR`` at a clean tmp dir for the test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(upload_dir):
    """Minimal FastAPI test app with only the catalog router."""
    from app.api.catalog import router

    app = FastAPI()
    app.include_router(router, prefix="/api/catalog")
    return TestClient(app)


def _write_catalog(upload_dir, takeoff_id: int, payload: dict) -> None:
    path = upload_dir / "analysis" / str(takeoff_id) / "catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


class TestHappyPath:
    def test_returns_saved_payload(self, client, upload_dir):
        payload = {
            "nodes": {"wall_0": {"id": "wall_0", "kind": "wall", "bbox_px": [0, 0, 10, 10]}},
            "edges": [],
            "metadata": {"schema_version": "4b-v1"},
        }
        _write_catalog(upload_dir, 42, payload)
        r = client.get("/api/catalog/42")
        assert r.status_code == 200
        assert r.json() == payload

    def test_empty_catalog_payload(self, client, upload_dir):
        _write_catalog(upload_dir, 1, {"nodes": {}, "edges": [], "metadata": {}})
        r = client.get("/api/catalog/1")
        assert r.status_code == 200
        assert r.json() == {"nodes": {}, "edges": [], "metadata": {}}


class TestNotFound:
    def test_missing_file_returns_404(self, client):
        r = client.get("/api/catalog/999")
        assert r.status_code == 404
        assert "999" in r.json()["detail"]

    def test_takeoff_id_zero_works(self, client, upload_dir):
        # Even takeoff_id 0 is valid path-wise; just check it 404s when no
        # file exists rather than choking on the int.
        r = client.get("/api/catalog/0")
        assert r.status_code == 404


class TestCorruptFile:
    def test_corrupt_json_returns_500(self, client, upload_dir):
        path = upload_dir / "analysis" / "5" / "catalog.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid {")
        r = client.get("/api/catalog/5")
        assert r.status_code == 500
        assert "JSON" in r.json()["detail"]


class TestPathLookup:
    def test_catalog_path_for_uses_settings_upload_dir(self, upload_dir):
        from app.api.catalog import _catalog_path_for

        path = _catalog_path_for(7)
        assert str(path).startswith(str(upload_dir))
        assert path.name == "catalog.json"
        assert "analysis" in path.parts
        assert "7" in path.parts
