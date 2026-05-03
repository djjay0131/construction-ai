# Active Context

Last updated: 2026-04-03

## Current State

The project has a working MVP for basic material takeoff from DXF/PDF floor plans. Recent work has focused on feature specification (3 specs written) and implementing the YOLO model storage/registry system. A test suite has been established for the first time.

## Recent Significant Changes

- **2026-04-03**: YOLO Model Storage feature VERIFIED — GCS bucket, model registry with hot-swap, publish CLI, 53 tests at 100% coverage. Terraform infrastructure deployed to `vt-gcp-00042` GCP project.
- **2026-04-01**: Specified 3 features via adversarial interview process:
  - Raster/Scanned Drawing Support (`llm/features/raster-scanned-drawing-support.md`) — SPECIFIED
  - OCR Dimension Extraction & Object Catalog (`llm/features/ocr-dimension-extraction.md`) — SPECIFIED
  - YOLO Model Storage (`llm/features/yolo-model-storage.md`) — VERIFIED
- **2026-03-31**: Created comprehensive feature backlog (`llm/features/BACKLOG.md`) consolidating all planned capabilities
- **2026-03-30**: Fixed backend dependency compatibility for Python 3.12
- **2026-03-06**: Added Euler-Bernoulli beam solver with verification and C++ benchmark

## Current Work Focus

Feature specification and implementation cycle. The model registry is the first feature to go through the full specify → implement → verify pipeline. Two more specs are ready for implementation.

## What's New Since Last Major Update

### Model Registry System (VERIFIED)
- `backend/app/core/ml/` — LiveModelRegistry with GCS-backed storage, hot-swap, generation pinning
- `backend/app/api/models.py` — API endpoints: list, status, activate (hot-swap), history
- `ml/models.yaml` — manifest as single source of truth for 3 YOLO models (5 versions total)
- `ml/publish.py` — CLI for publishing trained models to GCS
- `infra/main.tf` — Terraform config for GCS bucket + service account
- GCS bucket `gs://construction-ai-models/` deployed with versioning + lifecycle policy
- `backend/tests/` — 53 tests, 100% coverage (first test suite in the project)
- `DetectionService` and `FloorPlanAnalysisService` updated to use registry with legacy fallback

### Feature Specifications
- `llm/features/BACKLOG.md` — 45+ features organized by domain
- `llm/features/raster-scanned-drawing-support.md` — YOLO-constrained Hough lines for wall extraction from images, skew rejection, scale plausibility checking
- `llm/features/ocr-dimension-extraction.md` — EasyOCR dimension parsing, object catalog graph, OCR validates geometry (not overrides)

### Key Design Decisions Made During Specs
- **Skewed drawings are rejected** (not corrected) — applies to both raster and OCR specs
- **Scale-based geometry is primary**, OCR dimensions validate (not override)
- **Wall connections require line endpoint precision** (Hough lines, not YOLO bboxes)
- **Object catalog storage format is an experiment** — flat JSON default, graph optional
- **Model hot-swap is serialized** (max_workers=1) to limit memory

## Open Decisions

- Object catalog persistence format: flat JSON vs NetworkX graph (experiment deferred to agent work)
- Whether to proceed with Neo4j KG setup or continue with lightweight alternatives
- LLM provider choice for agent orchestration
- YOLO model retraining for scanned drawing robustness

## Immediate Next Steps

1. Implement **Raster/Scanned Drawing Support** (`/constellize:feature:implement raster-scanned-drawing-support`)
2. Implement **OCR Dimension Extraction** (`/constellize:feature:implement ocr-dimension-extraction`)
3. Specify and implement **Neo4j Setup** (`llm/features/neo4j-setup.md` exists but may need updating)
4. Specify and implement **Cut List Optimization** (OR-Tools, high user value)

## Reference

- Feature backlog: `llm/features/BACKLOG.md`
- Feature specs: `llm/features/*.md`
- Proposal vision: `memory-bank/` (synced from proposal repo)
- GCS models: `gs://construction-ai-models/`
- GCP project: `vt-gcp-00042`
