"""Tests for the ``/api/health/kg`` endpoint.

The router does a lazy ``from app import main as main_module`` at request
time so it can read the module-level ``_lumber_specs_cache`` and
``_kg_client``. The real ``app.main`` transitively imports the whole
backend (cv2, torch, etc.), which is heavyweight for unit tests, so we
stub ``app.main`` via ``sys.modules`` and mount only the health router
on a minimal FastAPI test app.
"""

from __future__ import annotations

import sys
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def stub_main(monkeypatch):
    """Install a stand-in for ``app.main`` so the router's lazy import works."""
    fake = types.ModuleType("app.main")
    fake._lumber_specs_cache = {}
    fake._kg_client = None
    monkeypatch.setitem(sys.modules, "app.main", fake)
    return fake


@pytest.fixture
def reset_uri(monkeypatch):
    """Default settings.NEO4J_URI = '' (disabled posture)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "NEO4J_URI", "")


@pytest.fixture
def client(stub_main, reset_uri):
    """Minimal FastAPI app with only the health router mounted."""
    from app.api.health import router

    app = FastAPI()
    app.include_router(router, prefix="/api/health")
    return TestClient(app)


class TestEndpointExists:
    def test_returns_200_with_required_keys(self, client):
        r = client.get("/api/health/kg")
        assert r.status_code == 200
        body = r.json()
        assert "kg_status" in body
        assert "lumber_specs_loaded" in body


class TestDisabledMode:
    def test_disabled_when_neo4j_uri_empty(self, client):
        r = client.get("/api/health/kg")
        assert r.json() == {"kg_status": "disabled", "lumber_specs_loaded": 0}

    def test_disabled_even_when_cache_somehow_populated(self, client, stub_main):
        # If NEO4J_URI is empty, disabled wins regardless of cache contents.
        stub_main._lumber_specs_cache = {(2, 4): object()}
        r = client.get("/api/health/kg")
        assert r.json() == {"kg_status": "disabled", "lumber_specs_loaded": 1}


class TestReadyMode:
    def test_ready_when_uri_set_client_present_cache_populated(
        self, client, stub_main, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "NEO4J_URI", "bolt+s://test.example")
        stub_main._kg_client = object()
        stub_main._lumber_specs_cache = {
            (i, j): object()
            for i, j in [(2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (4, 4)]
        }
        r = client.get("/api/health/kg")
        assert r.json() == {"kg_status": "ready", "lumber_specs_loaded": 6}


class TestErrorMode:
    def test_error_when_uri_set_but_client_none(
        self, client, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "NEO4J_URI", "bolt+s://test.example")
        # stub_main fixture default: _kg_client = None, cache empty
        r = client.get("/api/health/kg")
        assert r.json() == {"kg_status": "error", "lumber_specs_loaded": 0}

    def test_error_when_client_present_but_cache_empty(
        self, client, stub_main, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "NEO4J_URI", "bolt+s://test.example")
        stub_main._kg_client = object()
        # cache stays empty
        r = client.get("/api/health/kg")
        assert r.json() == {"kg_status": "error", "lumber_specs_loaded": 0}
