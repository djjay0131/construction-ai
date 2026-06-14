# Active Context

Last updated: 2026-06-06

## Current State

The project has a working MVP for basic material takeoff from DXF/PDF floor plans. Recent work has focused on feature specification (3 specs written) and implementing the YOLO model storage/registry system. A test suite has been established for the first time.

## Recent Significant Changes

- **2026-06-14**: Sprint 2 LIVE on GCP. Pivoted Neo4j hosting from AuraDB Free
  to self-hosted Community Edition on Compute Engine (no third-party SaaS
  dependency, no console.neo4j.io signup). Terraform additions: `e2-small`
  VM in us-east4-a + reserved internal IP (10.150.0.2) + dedicated runtime
  SA + 2 firewall rules (bolt from VPC connector, SSH from IAP) + Serverless
  VPC Access connector. Cloud Run service got a `vpc_access` block to reach
  the VM. Secret Manager versions now Terraform-managed (URI =
  `bolt://10.150.0.2:7687`, password from `random_password.neo4j.result`).
  Verified end-to-end: `systemctl is-active neo4j` → active; cypher-shell
  RETURN 1 → 1. Updated cost estimate: ~$25/mo (was ~$10/mo with Aura
  Free; VPC connector + always-on VM are the deltas). Spec addendum in
  sprint-2c spec; roadmap Section 2 updated. infra/README.md rewritten
  with the new operator runbook. Next: push these changes, watch CD run +
  smoke test the live URL.
- **2026-06-10** (latest): Sprint 2c (Aura deploy + smoke test) VERIFIED. All
  four gates pass: Gate 1 (47/47 tests, 100% coverage on both new modules),
  Gate 2 (no bare excepts, argparse validates --url, 5 distinct FAIL
  messages, endpoint always 200 for graceful degradation), Gate 3 (CI run
  #27300909633 green after a fix that added the new test files to the CI
  workflow; CD fails at auth as expected pre-Sprint-2c-live-step), Gate 4
  (all files compile, docstrings present, cd.yml parses with 12 steps).
  Sprint 2 of the 2026 Product Roadmap is now CODE-COMPLETE (2a + 2b + 2c
  all VERIFIED). **Next step is yours: enable GCP APIs, run
  `terraform apply`, capture WIF_PROVIDER + CI_SA_EMAIL outputs into GH
  secrets, provision AuraDB Free, populate the 3 Secret Manager secrets,
  push a commit; the next CD run will then run the live smoke test
  against the deployed Cloud Run URL.** Operator runbook at
  `infra/README.md`.
- **2026-06-10** (latest): Sprint 2c (Aura deploy + smoke test) IMPLEMENTED.
  Added `/api/health/kg` endpoint (returns kg_status + lumber_specs_loaded;
  always HTTP 200 so Cloud Run doesn't quarantine the revision),
  `backend/scripts/smoke_test.py` CLI (argparse + httpx; exit 0/1 with
  clear PASS/FAIL summary line), and 4-step smoke-test stanza in
  `.github/workflows/cd.yml` that runs after `gcloud run deploy` and fails
  CD when the new revision isn't `ready`. README sections added for
  AuraDB Free provisioning + first live smoke test. 17 new tests pass +
  100% coverage on both new modules; 30 Sprint 2a tests still pass
  (47/47 combined). Adversarial review caught the FastAPI heavy-import
  chain → restructured health test to use stub `app.main` via
  `sys.modules`. Spec at `llm/features/sprint-2c-aura-deploy-smoke-test.md`
  (IMPLEMENTED). **Sprint 2 is now fully implemented (2a + 2b + 2c).**
  Live verification of the smoke-test against a real Cloud Run URL waits
  on the user's manual setup (enable APIs, terraform apply, Aura
  provisioning, populate Secret Manager, set GH secrets).
- **2026-06-10** (later): Sprint 2b (CI/CD bootstrap + Terraform GCP) VERIFIED.
  All four quality gates pass after one Gate 1 fix (added `pytest`,
  `pytest-cov`, `pytest-asyncio`, `httpx`, `PyYAML` to `backend/requirements.txt`
  because CI builds a fresh venv and the local venv had them as side-effects
  of YOLO registry work). First successful CI run #27295044885 — install
  2m21s, tests 33s, all 30 pass, coverage uploaded. CD fails at auth step
  as expected (WIF_PROVIDER / CI_SA_EMAIL secrets not set yet; that's
  Sprint 2c). `terraform fmt -check` empty; HCL section dividers consistent
  with stars. Spec at `llm/features/sprint-2b-cicd-bootstrap-gcp.md`
  (VERIFIED). Sprint 2 progress: 2 of 3 sub-sprints complete. **Next: user
  enables GCP APIs + runs `terraform apply` + populates GH secrets + Aura
  Free; then Sprint 2c (live deploy + smoke test).**
- **2026-06-10**: Sprint 2b (CI/CD bootstrap + Terraform GCP) IMPLEMENTED.
  Added `.github/workflows/{ci,cd}.yml` (pytest with coverage on PR/master;
  WIF-auth build/push/deploy to Cloud Run on master). Extended `infra/main.tf`
  with Artifact Registry, Cloud Run v2 service, 3 Secret Manager secrets,
  Workload Identity Federation pool + provider, Cloud Run runtime SA, CI
  deployer SA with least-privilege IAM (AR writer + run.developer +
  iam.serviceAccountUser only). Added `infra/outputs.tf` and
  `infra/README.md` operator runbook. Backend Dockerfile updated so all
  three CMDs honor `$PORT`. Adversarial review caught Cloud Run
  chicken-and-egg → initial image now points at `cloudrun/container/hello`
  with `ignore_changes` on the image field. `terraform validate` Success;
  `terraform plan` 20 to add / 0 to change / 0 to destroy. 30/30 Sprint 2a
  tests still pass. Spec at `llm/features/sprint-2b-cicd-bootstrap-gcp.md`
  (IMPLEMENTED). Next: verify gates → user runs `terraform apply` →
  Sprint 2c (Aura provision + live deploy + smoke test).
- **2026-06-09**: Sprint 2a (Neo4j KG Foundation) VERIFIED. All four quality
  gates pass: Gate 1 30/30 tests + 100% line coverage on `app/core/kg/`
  (spec target 80%), Gate 2 defensive programming (no bare excepts, URI in
  error messages, graceful degradation when KG unavailable), Gate 3 no
  hardcoded secrets + `.env.example` has all NEO4J_* keys + `Settings` has
  3 fields + clean module imports, Gate 4 all files compile + every kg
  module has docstring. Spec at `llm/features/sprint-2a-neo4j-kg-foundation.md`
  (VERIFIED). Sprint 2 progress: 1 of 3 sub-sprints complete. Next: Sprint 2b
  (CI/CD + Terraform Cloud Run + AR + Secret Manager), then Sprint 2c (live
  Aura deploy + smoke test).
- **2026-06-08** (latest): Sprint 1c (VVUQ Phase 3 final review + 5→6 fix)
  VERIFIED. All four quality gates pass (Gate 1 AC grep coverage, Gate 2
  clean rebuild of both PDFs, Gate 3 in sync with origin/master and Pages
  Last-Modified 2026-06-09 03:58 UTC right after push, Gate 4 no rogue TikZ
  style). Cleaned up the stale "5 Specialized Agents" frame from Sprint 1b
  out-of-scope flag: now "6 Specialized Agents" with Structural in the ring;
  added structural agent node + arrows to the block-diagram frame too. Both
  PDFs recompiled clean (main 14 pp / 0 cite warnings; presentation 25 pp / 0
  errors). Final review record at
  `construction-ai-proposal/construction/design/vvuq-phase3-final-review.md`.
  Roadmap doc Appendix B updated: Sprint 0 + Sprint 1 marked DONE.
  **VVUQ Phase 3 — CLOSED 2026-06-08.** Sprint 1 of the 2026 Product Roadmap
  is complete. Next sprint: Sprint 2 — Neo4j Setup on GCP + CI/CD bootstrap.
- **2026-06-08** (later): Sprint 1b (VVUQ presentation slides) VERIFIED — all
  four quality gates pass (Gate 1 AC grep coverage, Gate 2 clean rebuild with
  0 errors and 0 Missing-$ warnings, Gate 3 in sync with origin/master, Gate 4
  no rogue colors/fonts, no new packages). New `\section{Structural Hypothesis
  Evaluation}` with 4 frames (Structural Challenge, Hypothesis Generation, PDE
  Evaluation, Verification Validation and Uncertainty Quantification) lives in
  `proposal/presentation.tex` between Agentic Workflow and Technology Stack;
  deck is now 25 slides. Out-of-scope discovery: existing "5 Specialized Agents"
  frame is stale (paper says 6 after VVUQ PR #6); flagged for future cleanup.
- **2026-06-08**: Sprint 1a (VVUQ structural-mechanics citations) VERIFIED — all
  four quality gates pass (Gate 1 AC grep coverage, Gate 2 clean recompile with
  0 final-pass citation warnings, Gate 3 in sync with origin/master, Gate 4
  bibtex style matches stars). 14 new bibitems live in `proposal/references.bib`
  with `\cite{}` anchors wired into `proposal/sections/05a-verification-validation.tex`.
  All web-verified (zero hallucinations; 3 metadata corrections logged in spec).
  Pre-existing "empty journal" warnings in anthropic2024claude, chase2022langchain,
  jocher2023yolov8 noted but out of scope.
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
