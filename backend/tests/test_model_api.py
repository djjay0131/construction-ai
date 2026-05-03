"""Tests for model management API endpoints."""

import yaml
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.models import router
from app.core.ml.model_registry import LiveModelRegistry


def _fake_loader(path):
    mock = MagicMock()
    mock._loaded_from = path
    return mock


def _create_app_with_registry(registry):
    """Create a test FastAPI app with a pre-configured registry."""
    app = FastAPI()
    app.include_router(router, prefix="/api/models")

    def override_registry():
        return registry

    from app.core.ml.model_registry import get_model_registry
    app.dependency_overrides[get_model_registry] = override_registry

    return app


def _setup_registry(tmp_path):
    """Create a registry with test data."""
    cache_dir = tmp_path / "cache"
    for model, version in [("model-a", "v1"), ("model-a", "v2"), ("model-b", "v1")]:
        d = cache_dir / model / version
        d.mkdir(parents=True)
        (d / "best.pt").write_bytes(b"fake")

    manifest = {
        "bucket": "test-bucket",
        "local_cache": str(cache_dir),
        "models": {
            "model-a": {
                "description": "Model A",
                "current_version": "v1",
                "versions": {
                    "v1": {"gcs_path": "model-a/v1/best.pt"},
                    "v2": {"gcs_path": "model-a/v2/best.pt"},
                },
            },
            "model-b": {
                "description": "Model B",
                "current_version": "v1",
                "versions": {
                    "v1": {"gcs_path": "model-b/v1/best.pt"},
                },
            },
        },
    }
    manifest_path = tmp_path / "models.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f)

    registry = LiveModelRegistry(str(manifest_path), model_loader=_fake_loader)
    registry.load_initial()
    return registry


class TestListModels:
    def test_returns_all_models(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.get("/api/models/list")
        assert response.status_code == 200
        data = response.json()
        names = [m["name"] for m in data["models"]]
        assert "model-a" in names
        assert "model-b" in names

    def test_includes_version_info(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.get("/api/models/list")
        models = {m["name"]: m for m in response.json()["models"]}
        assert models["model-a"]["active_version"] == "v1"
        assert set(models["model-a"]["available_versions"]) == {"v1", "v2"}


class TestModelStatus:
    def test_returns_active_versions(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.get("/api/models/status")
        assert response.status_code == 200
        active = response.json()["active_models"]
        assert active["model-a"] == "v1"
        assert active["model-b"] == "v1"


class TestActivateModel:
    def test_hot_swap_returns_success(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.post(
            "/api/models/model-a/activate",
            json={"version": "v2"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "model-a"
        assert data["to_version"] == "v2"
        assert data["status"] in ("started", "completed")

        # Wait for background completion
        registry._executor.shutdown(wait=True)

    def test_swap_nonexistent_model_returns_404(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.post(
            "/api/models/nonexistent/activate",
            json={"version": "v1"},
        )
        assert response.status_code == 404

    def test_swap_nonexistent_version_returns_404(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.post(
            "/api/models/model-a/activate",
            json={"version": "v99"},
        )
        assert response.status_code == 404

    def test_swap_to_same_version_returns_409(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.post(
            "/api/models/model-a/activate",
            json={"version": "v1"},
        )
        assert response.status_code == 409
        assert "already at version" in response.json()["detail"]


class TestSwapHistory:
    def test_empty_history(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        response = client.get("/api/models/history")
        assert response.status_code == 200
        assert response.json()["history"] == []

    def test_history_after_swap(self, tmp_path):
        registry = _setup_registry(tmp_path)
        client = TestClient(_create_app_with_registry(registry))

        client.post("/api/models/model-a/activate", json={"version": "v2"})
        registry._executor.shutdown(wait=True)

        response = client.get("/api/models/history")
        history = response.json()["history"]
        assert len(history) == 1
        assert history[0]["model_name"] == "model-a"
        assert history[0]["from_version"] == "v1"
        assert history[0]["to_version"] == "v2"
