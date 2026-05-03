"""
Live Model Registry
Manages YOLO model versions with hot-swap support.
Models are stored in GCS, cached locally, and loaded into memory.
"""

import logging
import threading
import yaml
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Resolved model metadata."""
    name: str
    version: str
    path: Path
    description: str = ""
    trained_at: Optional[str] = None
    dataset: Optional[str] = None
    metrics: dict = field(default_factory=dict)


@dataclass
class SwapEvent:
    """Record of a model swap operation."""
    model_name: str
    from_version: Optional[str]
    to_version: str
    timestamp: datetime
    status: str  # "started", "completed", "failed"
    error: Optional[str] = None


class LiveModelRegistry:
    """Model registry with GCS-backed storage and hot-swap support.

    Thread-safe: model reads are lock-protected, swaps are serialized
    via a single-worker thread pool to limit memory usage.
    """

    def __init__(self, manifest_path: str = "ml/models.yaml", model_loader=None):
        """Initialize the registry.

        Args:
            manifest_path: Path to models.yaml manifest
            model_loader: Callable that loads a model from a file path.
                         Defaults to YOLO constructor. Pass a custom loader
                         for testing without real YOLO models.
        """
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest()
        self._model_loader = model_loader or self._default_model_loader
        self._store = None
        self._models: dict[str, object] = {}
        self._versions: dict[str, str] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._swap_history: list[SwapEvent] = []

    @staticmethod
    def _default_model_loader(path: str):  # pragma: no cover — requires ultralytics + real .pt file
        from ultralytics import YOLO
        return YOLO(path)

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                f"Model manifest not found at {self.manifest_path}. "
                "Ensure ml/models.yaml exists in the project root."
            )
        with open(self.manifest_path) as f:
            manifest = yaml.safe_load(f)
        if not manifest or "models" not in manifest:
            raise ValueError(
                f"Invalid manifest at {self.manifest_path}: "
                "must contain a 'models' section."
            )
        return manifest

    @property
    def store(self):
        if self._store is None:
            from app.core.ml.model_store import GCSModelStore  # pragma: no cover — requires GCS credentials
            bucket = self.manifest.get("bucket")  # pragma: no cover
            if not bucket:  # pragma: no cover
                raise ValueError("Manifest missing 'bucket' field for GCS storage.")  # pragma: no cover
            self._store = GCSModelStore(bucket)  # pragma: no cover
        return self._store

    def _local_cache_path(self, gcs_path: str) -> Path:
        local_cache = Path(self.manifest.get("local_cache", "ml/models"))
        return local_cache / gcs_path

    def resolve(self, name: str, version: Optional[str] = None) -> ModelInfo:
        """Resolve a model name and version to a ModelInfo with a local file path.

        Downloads from GCS if not in local cache.
        """
        models = self.manifest.get("models", {})
        model_def = models.get(name)
        if not model_def:
            available = list(models.keys())
            raise KeyError(f"Model '{name}' not found. Available: {available}")

        version = version or model_def.get("current_version")
        if not version:
            raise KeyError(
                f"Model '{name}' has no current_version set in manifest."
            )

        versions = model_def.get("versions", {})
        ver_def = versions.get(version)
        if not ver_def:
            available = list(versions.keys())
            raise KeyError(
                f"Version '{version}' not found for '{name}'. Available: {available}"
            )

        gcs_path = ver_def.get("gcs_path")
        if not gcs_path:
            raise ValueError(
                f"Version '{version}' of '{name}' missing 'gcs_path' in manifest."
            )

        local_path = self._local_cache_path(gcs_path)

        if not local_path.exists():
            generation = ver_def.get("gcs_generation")
            logger.info(
                f"Model {name}:{version} not in cache, downloading from GCS"
            )
            self.store.download(gcs_path, local_path, generation)

        return ModelInfo(
            name=name,
            version=version,
            path=local_path,
            description=model_def.get("description", ""),
            trained_at=ver_def.get("trained_at"),
            dataset=ver_def.get("dataset"),
            metrics=ver_def.get("metrics", {}),
        )

    def load_initial(self):
        """Load all models at their current versions. Called at startup.

        Continues loading other models if one fails, logging errors.
        """
        models = self.manifest.get("models", {})
        for name in models:
            try:
                info = self.resolve(name)
                logger.info(f"Loading {name}:{info.version} from {info.path}")
                model = self._model_loader(str(info.path))
                with self._lock:
                    self._models[name] = model
                    self._versions[name] = info.version
                logger.info(f"Loaded {name}:{info.version}")
            except Exception as e:
                logger.error(
                    f"Failed to load model '{name}': {e}. "
                    "Service will start without this model."
                )

    def get_loaded_model(self, name: str) -> object:
        """Get the currently loaded model instance. Thread-safe fast read."""
        with self._lock:
            model = self._models.get(name)
        if model is None:
            raise RuntimeError(
                f"Model '{name}' not loaded. Check startup logs for errors."
            )
        return model

    def hot_swap(self, name: str, version: str) -> SwapEvent:
        """Swap to a new model version in the background.

        The new model is loaded in a background thread. Once loaded,
        the active model reference is atomically swapped under the lock.
        In-flight requests using the old model complete uninterrupted.

        Args:
            name: Model name (e.g., "yolo-objects")
            version: Target version (e.g., "v4")

        Returns:
            SwapEvent with initial status "started"
        """
        info = self.resolve(name, version)

        with self._lock:
            current = self._versions.get(name)
        if current == version:
            raise ValueError(f"'{name}' is already at version {version}")

        event = SwapEvent(
            model_name=name,
            from_version=current,
            to_version=version,
            timestamp=datetime.utcnow(),
            status="started",
        )
        self._swap_history.append(event)

        def _do_swap():
            try:
                logger.info(f"Hot-swap: loading {name}:{version} in background")
                new_model = self._model_loader(str(info.path))
                with self._lock:
                    self._models[name] = new_model
                    self._versions[name] = version
                event.status = "completed"
                logger.info(f"Hot-swap complete: {name} now at {version}")
            except Exception as e:
                event.status = "failed"
                event.error = str(e)
                logger.error(f"Hot-swap failed for {name}:{version}: {e}")

        self._executor.submit(_do_swap)
        return event

    def get_status(self) -> dict[str, str]:
        """Get currently active model versions."""
        with self._lock:
            return dict(self._versions)

    def get_swap_history(self) -> list[SwapEvent]:
        """Get the history of swap events."""
        return list(self._swap_history)

    def list_models(self) -> dict:
        """List all models and their versions from the manifest."""
        result = {}
        for name, model_def in self.manifest.get("models", {}).items():
            with self._lock:
                active_version = self._versions.get(name)
            result[name] = {
                "description": model_def.get("description", ""),
                "current_version": model_def.get("current_version"),
                "active_version": active_version,
                "available_versions": list(model_def.get("versions", {}).keys()),
            }
        return result


# Singleton
_registry: Optional[LiveModelRegistry] = None


def get_model_registry() -> LiveModelRegistry:  # pragma: no cover — singleton uses default paths + real YOLO loader
    """Get or create the global model registry singleton."""
    global _registry
    if _registry is None:
        _registry = LiveModelRegistry()
        _registry.load_initial()
    return _registry


def reset_model_registry():
    """Reset the singleton. Used for testing."""
    global _registry
    _registry = None
