# Feature: YOLO Model Storage & Registry

**Status:** VERIFIED
**Date:** 2026-04-01
**Author:** Feature Architect (AI-assisted)

## Problem

YOLO model weights (~50MB each) are stored inconsistently across the project: one model (`best.pt`) is committed directly to git as a 50MB binary, two others are referenced via relative paths to a `datascience/runs/` directory that is gitignored and doesn't exist on fresh clones. The config has a third path (`./ml/yolo/models/best.pt`) pointing to a directory that was never created. There is no versioning — when a model is retrained, the old weights are overwritten or lost. There is no way to swap between model versions without manually moving files and updating config. A fresh `git clone` + `docker-compose up` cannot start the CV pipeline because the models are missing or scattered.

## Goals

- Centralized model storage in GCS bucket with object versioning enabled, local cache under `ml/models/`
- A `models.yaml` manifest as the single source of truth for model names, versions, paths, and metadata
- A `LiveModelRegistry` that resolves model names to loaded YOLO instances with thread-safe hot-swapping (load new version in background, atomic cutover, zero downtime)
- An API endpoint to trigger model version swaps at runtime without restarting the service
- A fresh `git clone && docker-compose up` automatically downloads models from GCS on startup and starts serving

## Non-Goals

- Training pipeline integration (MLflow, W&B experiment tracking) — models are published manually to the registry after training
- Model A/B testing or canary deployment — swap is all-or-nothing
- Model format conversion (ONNX, TensorRT) — `.pt` files only for now
- Auto-scaling or multi-GPU model serving

## User Stories

- As a developer, I want to clone the repo and have all model weights download automatically from GCS on startup, so that the app works out of the box.
- As an ML engineer, I want to publish a newly trained model version to the registry and hot-swap it into the running service, so that I can test new models without redeploying.
- As an operator, I want to see which model versions are currently active and roll back to a previous version if a new model performs poorly, so that I can maintain service quality.

## Design Approach

### Architecture

```
GCS Bucket: gs://construction-ai-models/
  - Object versioning: enabled (prevents accidental loss from overwrites)
  - Lifecycle policy: delete noncurrent object versions after 90 days, but always retain at least 1 previous version (newerNoncurrentVersions=1 exemption)
  - Generation pinning: manifest includes gcs_generation per model version
├── yolo-boundary/
│   ├── v1/best.pt
│   └── v2/best.pt
├── yolo-objects/
│   ├── v1/best.pt
│   └── v3/best.pt
└── yolo-detection/
    └── v1/best.pt

Local (gitignored cache):
ml/
├── models.yaml                          # Manifest: model registry (checked into git)
├── models/                              # Local cache (gitignored), auto-downloaded from GCS
│   ├── yolo-boundary/v2/best.pt
│   ├── yolo-objects/v3/best.pt
│   └── yolo-detection/v1/best.pt
└── README.md

backend/app/core/ml/
├── model_registry.py                    # LiveModelRegistry with GCS download + hot-swap
├── model_store.py                       # GCS upload/download logic
└── model_schemas.py                     # Pydantic models for API responses

backend/app/api/
└── models.py                            # API endpoints for model management

ml/
├── publish.py                           # CLI helper: upload + capture generation + update manifest
└── models.yaml
```

### Data Flow

```
Startup:
  models.yaml → LiveModelRegistry
    → For each model: check local cache → if missing, download from GCS
    → Load current versions into memory → YOLO instances ready

Hot-swap request:
  POST /api/models/{name}/activate?version=v2
    → LiveModelRegistry.hot_swap(name, version)
    → Background thread: download from GCS if not cached → load YOLO
    → Atomic swap under lock
    → Old model garbage collected after in-flight requests complete

Detection request:
  DetectionService.detect_objects()
    → registry.get_loaded_model("yolo-objects")  # fast lock-protected read
    → model.predict(image)

Publish new model (via CLI helper):
  python -m ml.publish yolo-boundary v3 ./best.pt --dataset "exp4" --metrics '{"mAP50": 0.93}'
    → Uploads best.pt to gs://construction-ai-models/yolo-boundary/v3/best.pt
    → Captures GCS generation number automatically
    → Updates models.yaml with new version entry (gcs_path, gcs_generation, metadata)
    → Prints: "Published yolo-boundary:v3 (generation=1712016000000000)"
    → Developer commits models.yaml
    → Hot-swap via API (or restart to pick up new current_version)
```

### Key Components

1. **`models.yaml`** — Manifest file at `ml/models.yaml`. Declares model names, descriptions, current version, and per-version metadata (path, training date, dataset, metrics). Checked into git. This is the source of truth.

2. **`LiveModelRegistry`** (`backend/app/core/ml/model_registry.py`) — Singleton that loads models on startup, resolves names to loaded YOLO instances, and supports hot-swapping via background thread loading + atomic cutover. Thread-safe via `threading.RLock`.

3. **Model API** (`backend/app/api/models.py`) — Endpoints for listing models, checking active versions, triggering hot-swap, and viewing swap history.

4. **`ModelStore`** (`backend/app/core/ml/model_store.py`) — GCS upload/download logic with generation pinning. Used by both the registry (download) and the publish CLI (upload).

5. **Publish CLI** (`ml/publish.py`) — Single command to upload a model to GCS, capture the generation number, and update `models.yaml`. Usage: `python -m ml.publish <model-name> <version> <path-to-pt> [--dataset NAME] [--metrics JSON]`. Eliminates manual multi-step publishing.

6. **Config migration** — Remove `YOLO_MODEL_PATH`, `YOLO_BOUNDARY_MODEL_PATH`, `YOLO_OBJECT_MODEL_PATH` from `Settings`. Replace with `MODEL_MANIFEST_PATH: str = "ml/models.yaml"` and `GCS_MODEL_BUCKET: str` (from env or manifest).

### Manifest Schema

```yaml
# ml/models.yaml
bucket: "construction-ai-models"  # GCS bucket name
local_cache: "ml/models"          # local cache directory (gitignored)

models:
  yolo-boundary:
    description: "Floor plan boundary detection"
    current_version: "v2"
    versions:
      v1:
        gcs_path: "yolo-boundary/v1/best.pt"
        trained_at: "2026-01-14"
        dataset: "floorplan_boundary_exp1"
        metrics:
          mAP50: 0.82
          mAP50-95: 0.61
      v2:
        gcs_path: "yolo-boundary/v2/best.pt"
        gcs_generation: 1711929600000000    # pins to exact GCS object version
        trained_at: "2026-03-20"
        dataset: "floorplan_boundary_exp2"
        metrics:
          mAP50: 0.91
          mAP50-95: 0.72

  yolo-objects:
    description: "Floor plan object detection (walls, doors, windows, columns)"
    current_version: "v3"
    versions:
      v3:
        gcs_path: "yolo-objects/v3/best.pt"
        gcs_generation: 1710504000000000
        trained_at: "2026-03-15"
        dataset: "yolo12x_exp3"
        metrics:
          mAP50: 0.87

  yolo-detection:
    description: "General construction object detection"
    current_version: "v1"
    versions:
      v1:
        gcs_path: "yolo-detection/v1/best.pt"
        gcs_generation: 1705190400000000
        trained_at: "2026-01-14"
        dataset: "original_training"
        notes: "Migrated from backend/app/core/cv/best.pt"
```

## Sample Implementation

```python
# model_registry.py — LiveModelRegistry with hot-swap

import yaml
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ultralytics import YOLO

logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    name: str
    version: str
    path: Path
    description: str
    trained_at: Optional[str] = None
    dataset: Optional[str] = None
    metrics: dict = field(default_factory=dict)

@dataclass
class SwapEvent:
    model_name: str
    from_version: Optional[str]
    to_version: str
    timestamp: datetime
    status: str  # "started", "completed", "failed"
    error: Optional[str] = None

class LiveModelRegistry:
    """Model registry with hot-swap support."""

    def __init__(self, manifest_path: str = "ml/models.yaml"):
        self.manifest_path = Path(manifest_path)
        self.manifest = self._load_manifest()
        self._models: dict[str, YOLO] = {}          # name → loaded instance
        self._versions: dict[str, str] = {}          # name → active version
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1)  # serialize swaps to limit memory
        self._swap_history: list[SwapEvent] = []

    def _load_manifest(self) -> dict:
        with open(self.manifest_path) as f:
            return yaml.safe_load(f)

    def resolve(self, name: str, version: str = None) -> ModelInfo:
        """Resolve model name + version to ModelInfo. Downloads from GCS if not cached."""
        model_def = self.manifest["models"].get(name)
        if not model_def:
            available = list(self.manifest["models"].keys())
            raise KeyError(f"Model '{name}' not found. Available: {available}")

        version = version or model_def["current_version"]
        ver_def = model_def["versions"].get(version)
        if not ver_def:
            available = list(model_def["versions"].keys())
            raise KeyError(f"Version '{version}' not found for '{name}'. Available: {available}")

        # Local cache path
        local_cache = Path(self.manifest.get("local_cache", "ml/models"))
        local_path = local_cache / ver_def["gcs_path"]

        # Download from GCS if not in local cache
        if not local_path.exists():
            bucket = self.manifest["bucket"]
            generation = ver_def.get("gcs_generation")
            gcs_uri = f"gs://{bucket}/{ver_def['gcs_path']}"
            logger.info(f"Downloading {name}:{version} from {gcs_uri} (gen={generation})")
            self._download_from_gcs(bucket, ver_def["gcs_path"], local_path, generation)

        return ModelInfo(
            name=name, version=version, path=local_path,
            description=model_def.get("description", ""),
            trained_at=ver_def.get("trained_at"),
            dataset=ver_def.get("dataset"),
            metrics=ver_def.get("metrics", {}),
        )

    def _download_from_gcs(self, bucket: str, gcs_path: str, local_path: Path,
                           generation: int = None):
        """Download a model file from GCS to local cache.
        
        Uses generation number to pin to an exact object version,
        preventing silent corruption from overwrites.
        """
        from google.cloud import storage
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client = storage.Client()
        blob = client.bucket(bucket).blob(gcs_path, generation=generation)
        blob.download_to_filename(str(local_path))
        logger.info(f"Downloaded {gcs_path} (gen={generation}) → {local_path} "
                     f"({local_path.stat().st_size / 1e6:.1f}MB)")

    def load_initial(self):
        """Load all models at their current versions. Called at startup."""
        for name in self.manifest["models"]:
            info = self.resolve(name)
            logger.info(f"Loading {name}:{info.version} from {info.path}")
            model = YOLO(str(info.path))
            with self._lock:
                self._models[name] = model
                self._versions[name] = info.version
            logger.info(f"Loaded {name}:{info.version}")

    def get_loaded_model(self, name: str) -> YOLO:
        """Get currently loaded model instance. Thread-safe fast read."""
        with self._lock:
            model = self._models.get(name)
        if not model:
            raise RuntimeError(f"Model '{name}' not loaded")
        return model

    def hot_swap(self, name: str, version: str) -> SwapEvent:
        """Load new version in background, atomic swap when ready."""
        info = self.resolve(name, version)  # validate before background load

        with self._lock:
            current = self._versions.get(name)
        if current == version:
            raise ValueError(f"{name} is already at version {version}")

        event = SwapEvent(
            model_name=name, from_version=current,
            to_version=version, timestamp=datetime.utcnow(),
            status="started"
        )
        self._swap_history.append(event)

        def _do_swap():
            try:
                logger.info(f"Hot-swap: loading {name}:{version} in background")
                new_model = YOLO(str(info.path))
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

    def get_status(self) -> dict:
        with self._lock:
            return dict(self._versions)

    def get_swap_history(self) -> list[SwapEvent]:
        return list(self._swap_history)


# Singleton
_registry: Optional[LiveModelRegistry] = None

def get_model_registry() -> LiveModelRegistry:
    global _registry
    if _registry is None:
        _registry = LiveModelRegistry()
        _registry.load_initial()
    return _registry
```

## Edge Cases & Error Handling

### GCS Download Failure
- **Scenario**: GCS is unreachable, credentials are missing, or bucket doesn't exist.
- **Behavior**: `_download_from_gcs()` raises with a clear message: "Failed to download model from GCS. Check GOOGLE_APPLICATION_CREDENTIALS and bucket permissions." If local cache exists from a previous download, fall back to cached version with a warning.
- **Test**: Revoke credentials, attempt startup. Verify error message. Then restore cache file, verify fallback works.

### No GCS Credentials
- **Scenario**: Developer doesn't have a GCP service account key configured.
- **Behavior**: Startup fails with a clear message listing what's needed: `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to a service account JSON key with `storage.objects.get` permission on the bucket.
- **Test**: Unset credentials env var, attempt startup, verify error message.

### Hot-Swap During Active Requests
- **Scenario**: Detection request is in-flight using model v2 when hot-swap replaces it with v3.
- **Behavior**: The in-flight request holds a Python reference to the v2 YOLO object. The swap replaces the dict entry, but the in-flight request completes using v2. v2 is garbage collected only after all references are released. No request is interrupted.
- **Test**: Start a slow detection, trigger hot-swap mid-request, verify both complete successfully.

### Hot-Swap to Nonexistent Version
- **Scenario**: API request to swap to version "v99" which doesn't exist in manifest.
- **Behavior**: `resolve()` raises `KeyError` synchronously before any background work starts. API returns 404 with available versions listed.
- **Test**: Call swap endpoint with invalid version, verify 404 response with version list.

### Concurrent Hot-Swaps
- **Scenario**: Two swap requests arrive simultaneously (e.g., swap boundary and objects models at once).
- **Behavior**: Swaps are serialized via a single-worker thread pool (`max_workers=1`) to prevent memory spikes from loading multiple models simultaneously. The second swap queues behind the first. API returns immediately for both with "started" status; the caller checks `/status` to see completion order.
- **Test**: Trigger two swaps concurrently, verify they execute sequentially (second completes after first) and peak memory stays within bounds.

### Model File Corrupted
- **Scenario**: `.pt` file is truncated or corrupted.
- **Behavior**: YOLO constructor raises an exception. For startup: fail fast with clear error. For hot-swap: log error, keep previous version active, mark swap event as "failed".
- **Test**: Provide a truncated `.pt` file, verify startup fails clearly and hot-swap preserves old model.

### Manifest References Missing GCS Object
- **Scenario**: Manifest references a version that doesn't exist in GCS (typo, forgot to upload, deleted).
- **Behavior**: On startup or hot-swap, `_download_from_gcs()` fails with a clear error: "Model '{name}:{version}' not found in GCS at gs://{bucket}/{path}. Verify the file was uploaded." The service continues with other models that loaded successfully — only the missing model is unavailable.
- **Test**: Add a manifest entry pointing to a nonexistent GCS path, verify startup logs the error and other models load normally.

### Startup Manifest Validation
- **Scenario**: App starts and needs to verify all `current_version` entries in the manifest actually exist in GCS before loading.
- **Behavior**: On startup, `load_initial()` performs a lightweight HEAD check against GCS for each model's `current_version` before downloading. Any missing models are logged as errors with the exact `gsutil cp` command needed to fix it. The app still starts with whatever models are available.
- **Test**: Remove one model from GCS, start the app, verify the missing model is logged with a remediation command and the other models load.

## Acceptance Criteria

### AC-1: Automatic GCS Download
- **Given** a fresh `git clone` with GCS credentials configured
- **When** the application starts
- **Then** all model files are automatically downloaded from GCS to `ml/models/{name}/{version}/best.pt` local cache

### AC-2: Manifest as Source of Truth
- **Given** the `ml/models.yaml` manifest
- **When** the app starts
- **Then** each model listed is loaded at its `current_version` and the manifest is the only config needed (no env vars for model paths)

### AC-3: Startup Model Loading
- **Given** a properly configured manifest with valid model files
- **When** the application starts
- **Then** all models are loaded into memory and the detection services are operational

### AC-4: Hot-Swap via API
- **Given** a running service with `yolo-objects:v3` loaded
- **When** `POST /api/models/yolo-objects/activate?version=v4` is called
- **Then** v4 loads in the background, requests continue serving with v3 until v4 is ready, then v4 becomes active with zero dropped requests

### AC-5: Swap Status and History
- **Given** a hot-swap has been triggered
- **When** `GET /api/models/status` is called
- **Then** the response shows each model's active version and the swap history (timestamps, from/to versions, status)

### AC-6: Rollback
- **Given** `yolo-objects` was swapped from v3 to v4
- **When** `POST /api/models/yolo-objects/activate?version=v3` is called
- **Then** v3 is reloaded and becomes active (rollback is just another swap)

### AC-7: Config Migration
- **Given** the old config with `YOLO_MODEL_PATH`, `YOLO_BOUNDARY_MODEL_PATH`, `YOLO_OBJECT_MODEL_PATH`
- **When** the registry is implemented
- **Then** those settings are removed and replaced with `MODEL_MANIFEST_PATH`, and `DetectionService` + `FloorPlanAnalysisService` use `registry.get_loaded_model()` instead of direct YOLO construction

### AC-8: GCS Bucket Setup
- **Given** a GCP project with billing enabled
- **When** the bucket is created
- **Then** `gs://construction-ai-models/` exists with object versioning enabled, and all 3 models are uploaded to their correct paths

### AC-9: Clear Error on Missing Credentials
- **Given** a fresh environment with no GCS credentials and no local model cache
- **When** the app attempts to start
- **Then** startup fails with a clear error message explaining how to configure `GOOGLE_APPLICATION_CREDENTIALS`

### AC-10: Local Cache Reuse
- **Given** models were previously downloaded to `ml/models/`
- **When** the app starts again
- **Then** cached models are loaded directly without contacting GCS

### AC-11: Generation Pinning
- **Given** a model version with a `gcs_generation` in the manifest
- **When** someone overwrites the GCS object at that path with a different file
- **Then** the registry still downloads the original pinned version, not the overwrite

### AC-12: Lifecycle Policy
- **Given** the GCS bucket
- **When** a lifecycle policy is configured
- **Then** noncurrent object versions older than 90 days are automatically deleted, EXCEPT the most recent noncurrent version is always retained regardless of age, and current (pinned) versions are never affected

### AC-13: Publish CLI
- **Given** a trained model file `best.pt` on disk
- **When** `python -m ml.publish yolo-boundary v3 ./best.pt --dataset "exp4"` is run
- **Then** the file is uploaded to GCS, the generation number is captured, `models.yaml` is updated with the new version entry, and the CLI prints a confirmation with the generation number

### AC-14: Model Migration
- **Given** the existing `backend/app/core/cv/best.pt`
- **When** migration is complete
- **Then** the file is uploaded to `gs://construction-ai-models/yolo-detection/v1/best.pt`, the old file is removed from git tracking, and `ml/models/` is added to `.gitignore`

## Technical Notes

- **Affected components:**
  - `backend/app/core/config.py` — remove `YOLO_MODEL_PATH`, `YOLO_BOUNDARY_MODEL_PATH`, `YOLO_OBJECT_MODEL_PATH`; add `MODEL_MANIFEST_PATH`
  - `backend/app/core/cv/detection_service.py` — replace `YOLO(model_path)` with `registry.get_loaded_model("yolo-detection")`
  - `backend/app/core/cv/floor_plan_service.py` — replace `YOLO(settings.YOLO_BOUNDARY_MODEL_PATH)` and `YOLO(settings.YOLO_OBJECT_MODEL_PATH)` with registry lookups
  - `backend/app/core/ml/model_registry.py` — new: `LiveModelRegistry`
  - `backend/app/api/models.py` — new: model management API endpoints
  - `ml/models.yaml` — new: model manifest
  - `ml/models/` — new: standardized model directory
  - `.gitattributes` — new: Git LFS tracking rules
  - `backend/app/core/cv/best.pt` — removed from git, uploaded to GCS as `yolo-detection/v1/best.pt`
  - `docker-compose.yml` — `./ml:/app/ml` volume mount already exists; add `GOOGLE_APPLICATION_CREDENTIALS` env var
  - `.gitignore` — add `ml/models/` (local cache, downloaded from GCS)

- **Patterns to follow:**
  - Singleton pattern with `get_model_registry()` (matches `get_detection_service()`, `get_floor_plan_service()`)
  - Pydantic schemas for API responses
  - FastAPI dependency injection via `Depends(get_model_registry)`

- **Data model changes:** None. Models are files, not database records.

- **Dependencies:**
  - `pyyaml` — for manifest parsing (likely already installed as transitive dep, verify)
  - `google-cloud-storage` — GCS client library (new)
  - `GOOGLE_APPLICATION_CREDENTIALS` env var — service account key for GCS access

## Dependencies

- **GCP Project** — with billing enabled and a GCS bucket created (`construction-ai-models`)
- **`google-cloud-storage`** — Python client library, must be added to `requirements.txt`
- **Service account** — with `storage.objects.get` and `storage.objects.create` permissions on the bucket. Key file referenced by `GOOGLE_APPLICATION_CREDENTIALS` env var.
- **Existing `DetectionService`** and **`FloorPlanAnalysisService`** — both must be refactored to use `registry.get_loaded_model()` instead of constructing YOLO instances directly.

## Open Questions

- **GCS bucket naming and project:** The bucket name `construction-ai-models` is a placeholder. Actual name depends on GCP project setup. Bucket names are globally unique.
- **Publish CLI flags:** Should the CLI auto-set `current_version` to the newly published version, or leave that as a separate manual edit? Auto-setting is convenient but risky if you want to publish without activating.
- **Startup time:** Downloading 3 models (~150MB total) on first startup + loading into memory could take 30-60 seconds. Should models download/load lazily (on first request) or eagerly (at startup, blocking the server)?
- **Authentication for model swap API:** The hot-swap endpoint can change what model the service uses. Should it require authentication/admin access? Currently the app has no auth (backlog 10.5).
- **Service account distribution:** How will developers get the GCS service account key? Shared secret in a password manager? Per-developer keys? This affects the onboarding experience.
