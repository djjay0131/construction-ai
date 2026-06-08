# Active Context

Last updated: 2026-06-06

## Current State

The project has a working MVP for basic material takeoff from DXF/PDF floor plans. Recent work has focused on feature specification (3 specs written) and implementing the YOLO model storage/registry system. A test suite has been established for the first time.

## Recent Significant Changes

- **2026-06-08**: Sprint 1a (VVUQ structural-mechanics citations) IMPLEMENTED —
  14 new bibitems added to `proposal/references.bib` (V&V, ASME standards, GCI,
  beam theory, FEM, MC, LHS, UQ, reliability, MOO) with `\cite{}` anchors wired
  into `proposal/sections/05a-verification-validation.tex`. All 14 web-verified
  (zero hallucinations; 3 metadata corrections logged in spec). `main.pdf`
  compiles to 14 pages with 0 undefined-citation warnings. Spec at
  `llm/features/sprint-1a-vvuq-structural-mechanics-citations.md` (status:
  IMPLEMENTED). Next: verify gates, then Sprint 1b (presentation slides).
- **2026-06-07**: Sprint 0 of 2026 Product Roadmap VERIFIED — four quality gates
  pass (adapted for markdown feature: AC grep coverage, cross-ref resolution,
  commit+push to origin, format consistency). Gate 2 caught two residual stale
  "PR #7 pending merge" phrases in proposal `progress.md`; fixed in commit 0f58f50.
- **2026-06-06**: Sprint 0 of 2026 Product Roadmap IMPLEMENTED — memory-bank refresh
  in both repos. Spec at `llm/features/sprint-0-memory-bank-refresh.md`. Pivots
  from CS6444 (submitted 2026-05-11) back to product work. Canonical roadmap:
  `../construction-ai-proposal/construction/design/2026-product-roadmap.md`
  (committed ae095ae). Pointer: `llm/features/ROADMAP.md` (06d7e0e).
- **2026-05-11**: CS6444 Final Project SUBMITTED at tag
  `final-project-submitted-2026-05-11` (master @ 63f3d7a). Microllam 2.0E baseline.
  HW2–5 + Final Project all live on Pages. 25 bibliography entries web-verified.
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

Per the 2026 Product Roadmap (sprint sequence locked 2026-06-06):

1. **Sprint 1** — VVUQ Phase 3 closeout (proposal repo; 4 slides + 10–15 citations + final review)
2. **Sprint 2** — Implement Neo4j Setup (`/constellize:feature:implement neo4j-setup`)
   - Pre-requisites: provision AuraDB Free (prod + ci-test), update spec date if needed
   - Includes CI/CD bootstrap and Terraform extensions
3. **Sprint 3** — Implement Raster/Scanned Drawing Support (`/constellize:feature:implement raster-scanned-drawing-support`)
4. **Sprint 4** — Implement OCR Dimension Extraction (`/constellize:feature:implement ocr-dimension-extraction`)
5. **Sprint 5** — Phase 1 integration smoke test against 2–3 plan sets

Source of truth: `../construction-ai-proposal/construction/design/2026-product-roadmap.md`
(also pointed to from `llm/features/ROADMAP.md`).

## Reference

- Feature backlog: `llm/features/BACKLOG.md`
- Feature specs: `llm/features/*.md`
- Proposal vision: `memory-bank/` (synced from proposal repo)
- GCS models: `gs://construction-ai-models/`
- GCP project: `vt-gcp-00042`
