"""Tests for LiveModelRegistry."""

import time
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock

from app.core.ml.model_registry import LiveModelRegistry, reset_model_registry


def _write_manifest(tmp_path, manifest_data):
    """Helper to write a manifest file and return its path."""
    manifest_path = tmp_path / "models.yaml"
    with open(manifest_path, "w") as f:
        yaml.dump(manifest_data, f)
    return manifest_path


def _minimal_manifest(tmp_path, model_file=None):
    """Create a minimal valid manifest with a cached model file."""
    if model_file is None:
        cache_dir = tmp_path / "cache" / "test-model" / "v1"
        cache_dir.mkdir(parents=True)
        model_file = cache_dir / "best.pt"
        model_file.write_bytes(b"fake model")

    return {
        "bucket": "test-bucket",
        "local_cache": str(tmp_path / "cache"),
        "models": {
            "test-model": {
                "description": "Test model",
                "current_version": "v1",
                "versions": {
                    "v1": {
                        "gcs_path": "test-model/v1/best.pt",
                        "gcs_generation": 12345,
                        "trained_at": "2026-01-01",
                        "metrics": {"mAP50": 0.9},
                    },
                    "v2": {
                        "gcs_path": "test-model/v2/best.pt",
                        "gcs_generation": 67890,
                        "trained_at": "2026-02-01",
                    },
                },
            }
        },
    }


def _fake_loader(path):
    """Fake model loader that returns a mock instead of loading YOLO."""
    mock = MagicMock()
    mock._loaded_from = path
    return mock


class TestManifestLoading:
    def test_loads_valid_manifest(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        assert "test-model" in registry.manifest["models"]

    def test_missing_manifest_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Model manifest not found"):
            LiveModelRegistry(str(tmp_path / "nonexistent.yaml"))

    def test_empty_manifest_raises(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        with pytest.raises(ValueError, match="Invalid manifest"):
            LiveModelRegistry(str(path))

    def test_manifest_without_models_raises(self, tmp_path):
        path = _write_manifest(tmp_path, {"bucket": "test"})
        with pytest.raises(ValueError, match="must contain a 'models' section"):
            LiveModelRegistry(str(path))


class TestResolve:
    def test_resolve_current_version(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        info = registry.resolve("test-model")
        assert info.name == "test-model"
        assert info.version == "v1"
        assert info.metrics == {"mAP50": 0.9}

    def test_resolve_specific_version(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        # Create cache file for v2
        cache_dir = tmp_path / "cache" / "test-model" / "v2"
        cache_dir.mkdir(parents=True)
        (cache_dir / "best.pt").write_bytes(b"fake v2")

        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        info = registry.resolve("test-model", "v2")
        assert info.version == "v2"

    def test_resolve_unknown_model_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        with pytest.raises(KeyError, match="not found.*Available"):
            registry.resolve("nonexistent")

    def test_resolve_unknown_version_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        with pytest.raises(KeyError, match="Version 'v99' not found.*Available"):
            registry.resolve("test-model", "v99")

    def test_resolve_downloads_from_gcs_when_not_cached(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        # Remove the cached file for v1
        cache_file = tmp_path / "cache" / "test-model" / "v1" / "best.pt"
        if cache_file.exists():
            cache_file.unlink()

        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        mock_store = MagicMock()
        mock_store.download = MagicMock(
            side_effect=lambda gcs_path, local_path, gen: local_path.parent.mkdir(parents=True, exist_ok=True) or local_path.write_bytes(b"downloaded")
        )
        registry._store = mock_store

        info = registry.resolve("test-model", "v1")
        mock_store.download.assert_called_once_with(
            "test-model/v1/best.pt",
            cache_file,
            12345,
        )
        assert info.path == cache_file

    def test_resolve_uses_cache_when_available(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        mock_store = MagicMock()
        registry._store = mock_store

        registry.resolve("test-model", "v1")
        mock_store.download.assert_not_called()

    def test_resolve_missing_gcs_path_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        manifest["models"]["test-model"]["versions"]["v1"].pop("gcs_path")
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        with pytest.raises(ValueError, match="missing 'gcs_path'"):
            registry.resolve("test-model", "v1")

    def test_resolve_no_current_version_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        del manifest["models"]["test-model"]["current_version"]
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        with pytest.raises(KeyError, match="no current_version"):
            registry.resolve("test-model")


class TestLoadInitial:
    def test_loads_all_models(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        registry.load_initial()

        status = registry.get_status()
        assert status == {"test-model": "v1"}

    def test_continues_on_failure(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        manifest["models"]["bad-model"] = {
            "description": "Will fail",
            "current_version": "v1",
            "versions": {
                "v1": {"gcs_path": "bad/v1/best.pt"},
            },
        }
        path = _write_manifest(tmp_path, manifest)

        call_count = 0

        def selective_loader(p):
            nonlocal call_count
            call_count += 1
            if "bad" in p:
                raise RuntimeError("corrupt model")
            return _fake_loader(p)

        registry = LiveModelRegistry(str(path), model_loader=selective_loader)
        # Mock store to handle the missing bad-model file
        mock_store = MagicMock()
        mock_store.download = MagicMock(
            side_effect=lambda gcs_path, local_path, gen: (
                local_path.parent.mkdir(parents=True, exist_ok=True)
                or local_path.write_bytes(b"bad")
            )
        )
        registry._store = mock_store

        registry.load_initial()

        status = registry.get_status()
        assert "test-model" in status
        assert "bad-model" not in status


class TestGetLoadedModel:
    def test_returns_loaded_model(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        model = registry.get_loaded_model("test-model")
        assert model is not None

    def test_unloaded_model_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)

        with pytest.raises(RuntimeError, match="not loaded"):
            registry.get_loaded_model("test-model")


class TestHotSwap:
    def test_swap_changes_active_version(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        # Create cache for v2
        v2_dir = tmp_path / "cache" / "test-model" / "v2"
        v2_dir.mkdir(parents=True)
        (v2_dir / "best.pt").write_bytes(b"v2 model")

        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        event = registry.hot_swap("test-model", "v2")
        assert event.from_version == "v1"
        assert event.to_version == "v2"

        # Wait for background thread
        registry._executor.shutdown(wait=True)

        assert event.status == "completed"
        assert registry.get_status()["test-model"] == "v2"

    def test_swap_to_same_version_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        with pytest.raises(ValueError, match="already at version"):
            registry.hot_swap("test-model", "v1")

    def test_swap_to_nonexistent_version_raises(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        with pytest.raises(KeyError, match="Version 'v99' not found"):
            registry.hot_swap("test-model", "v99")

    def test_failed_swap_preserves_old_model(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        v2_dir = tmp_path / "cache" / "test-model" / "v2"
        v2_dir.mkdir(parents=True)
        (v2_dir / "best.pt").write_bytes(b"corrupt")

        path = _write_manifest(tmp_path, manifest)

        load_count = 0

        def failing_on_v2(p):
            nonlocal load_count
            load_count += 1
            if "v2" in p:
                raise RuntimeError("corrupt model file")
            return _fake_loader(p)

        registry = LiveModelRegistry(str(path), model_loader=failing_on_v2)
        registry.load_initial()

        event = registry.hot_swap("test-model", "v2")
        registry._executor.shutdown(wait=True)

        assert event.status == "failed"
        assert "corrupt" in event.error
        assert registry.get_status()["test-model"] == "v1"

    def test_swap_records_history(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        v2_dir = tmp_path / "cache" / "test-model" / "v2"
        v2_dir.mkdir(parents=True)
        (v2_dir / "best.pt").write_bytes(b"v2")

        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        registry.hot_swap("test-model", "v2")
        registry._executor.shutdown(wait=True)

        history = registry.get_swap_history()
        assert len(history) == 1
        assert history[0].model_name == "test-model"
        assert history[0].to_version == "v2"
        assert history[0].status == "completed"

    def test_rollback_is_just_another_swap(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        v2_dir = tmp_path / "cache" / "test-model" / "v2"
        v2_dir.mkdir(parents=True)
        (v2_dir / "best.pt").write_bytes(b"v2")

        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        # Swap to v2
        registry.hot_swap("test-model", "v2")
        registry._executor.shutdown(wait=True)
        assert registry.get_status()["test-model"] == "v2"

        # Need a new executor since we shut down the old one
        from concurrent.futures import ThreadPoolExecutor
        registry._executor = ThreadPoolExecutor(max_workers=1)

        # Rollback to v1
        registry.hot_swap("test-model", "v1")
        registry._executor.shutdown(wait=True)
        assert registry.get_status()["test-model"] == "v1"

        assert len(registry.get_swap_history()) == 2


class TestListModels:
    def test_list_includes_all_info(self, tmp_path):
        manifest = _minimal_manifest(tmp_path)
        path = _write_manifest(tmp_path, manifest)
        registry = LiveModelRegistry(str(path), model_loader=_fake_loader)
        registry.load_initial()

        models = registry.list_models()
        assert "test-model" in models
        info = models["test-model"]
        assert info["description"] == "Test model"
        assert info["current_version"] == "v1"
        assert info["active_version"] == "v1"
        assert set(info["available_versions"]) == {"v1", "v2"}


class TestSerializedSwaps:
    def test_swaps_execute_sequentially(self, tmp_path):
        """Verify that concurrent swaps are serialized (max_workers=1)."""
        manifest = _minimal_manifest(tmp_path)
        # Add a third version
        manifest["models"]["test-model"]["versions"]["v3"] = {
            "gcs_path": "test-model/v3/best.pt",
        }
        for v in ["v2", "v3"]:
            d = tmp_path / "cache" / "test-model" / v
            d.mkdir(parents=True, exist_ok=True)
            (d / "best.pt").write_bytes(b"fake")

        path = _write_manifest(tmp_path, manifest)

        execution_order = []

        def tracking_loader(p):
            time.sleep(0.05)  # small delay to test ordering
            version = Path(p).parent.name
            execution_order.append(version)
            return _fake_loader(p)

        registry = LiveModelRegistry(str(path), model_loader=tracking_loader)
        registry.load_initial()

        # Trigger two swaps concurrently
        registry.hot_swap("test-model", "v2")
        registry.hot_swap("test-model", "v3")
        registry._executor.shutdown(wait=True)

        # Both should have executed (serialized), final state is v3
        assert registry.get_status()["test-model"] == "v3"
        assert len(registry.get_swap_history()) == 2


class TestSingleton:
    def test_reset_clears_singleton(self):
        reset_model_registry()
        from app.core.ml.model_registry import _registry
        assert _registry is None
