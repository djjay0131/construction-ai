# Progress

Last updated: 2026-07-08

## What Is Built and Working

### Plan Parsing Pipeline (Phase 1)
- **DXF parsing** via ezdxf — extracts wall geometry as LINE/LWPOLYLINE entities (`parsers/dxf_parser.py`).
- **DWG→DXF auto-conversion** via LibreDWG (`parsers/dwg_converter.py`).
- **PDF vector extraction** via PyMuPDF (`parsers/pdf_parser.py`) — post-Sprint-4f handles 5 path-item shapes (`m`, `l` in both forms, `re`, `qu`, `c`) with scale detection cascade (manual > auto_text > 1:1 fallback with `scale_warning`) and 1-inch minimum wall length filter.
- **Multi-page PDF dispatch** (`pdf_takeoff.py`) — vector-first per page; pages with zero vector walls rasterize at `settings.PDF_DPI` and run the Sprint 3b/4d raster pipeline. Walls tagged `metadata["source"] ∈ {pdf_vector, pdf_raster}` and `metadata["page"]`.
- **Raster/scanned drawing support** (`parsers/raster_parser.py`, `cv/*`) — image preprocess → skew reject → YOLO-constrained Hough line extraction → 3-tier scale detection (reference measurement > manual > ScaleWarning fallback) → pixel-to-inch coord conversion.

### Material Takeoff Calculation
- Stud calculation with configurable spacing (12"/16"/24" O.C.).
- Top and bottom plate calculation (single or double top plate).
- Lumber specification database (6 KG-served specs; nominal vs actual dimensions).
- **Rule-cited BOM** — `LumberCalculator(kg_client=...)` populates `rule_citations: list[str]` (IRC R602.3.x etc.) and `source_walls: list[str]` (page-tagged wall IDs) on every `LumberMaterialItem`.
- JSON-formatted material list output.

### OCR + Object Catalog (Phase 1)
- **Dimension parser** (`cv/dimension_parser.py`) — regex-based; imperial ft-in, fractional, inches-only, word-form, metric mm/m; `parse_many` survives partial failures.
- **Dimension extractor** (`cv/dimension_extractor.py`) — Protocol-typed `OcrReader`; returns `(parsed_dimensions, raw_texts)`.
- **EasyOCR reader** (`cv/easyocr_reader.py`) — lazy-init; quad-points → axis-aligned bbox; implements OcrReader Protocol.
- **Spatial associator** (`catalog/spatial_association.py`) — pairs dimensions to catalog nodes by bbox-centroid distance with deterministic tie-breaking.
- **Catalog builder** (`catalog/catalog_builder.py`) — wall-wall CONNECTS_TO, wall-opening CONTAINS edges; OCR-vs-geometry validation (<10% confirmed / 10-15% minor_discrepancy / >15% mismatch + flag).
- **Catalog store** (`catalog/catalog_store.py`) — JSON round-trip with parent-dir creation; missing-file and corrupt-JSON raise.
- **Validation summary** (`catalog/validation_summary.py`) — counts confirmed / minor / mismatch / unvalidated walls.
- **Catalog API** — `GET /api/catalog/{takeoff_id}` (`api/catalog.py`).

### Neo4j Knowledge Graph (Sprint 2)
- **KG client** (`core/kg/`) — Neo4j Bolt driver + connection lifecycle + graceful degradation when KG unavailable (`get_kg_client()` factory returns None on connect failure, health endpoint stays 200).
- **KG loader** — seeds 6 lumber specs (`lumber_specs_loaded=6` in health payload).
- **Rule provenance** — `cite_rule_for(item)` returns IRC/IBC citations for stud, plate, header decisions.
- **Health endpoint** — `GET /api/health/kg` returns `kg_status ∈ {ready, degraded}` + `lumber_specs_loaded`.

### Computer Vision (Sprint 3)
- **ImagePreprocessor** — skew detection, threshold rejection, CLAHE enhance, Gaussian denoise.
- **CoordinateConverter** — pixel→inch conversion produces `WallElement[]`.
- **WallLineExtractor** — YOLO-constrained Hough (Protocol-based `LineDetector` DI so tests don't load torch/ultralytics). `last_detections` caches per-`extract()` run for catalog reuse.
- **ScaleDetector** — reference → manual → ScaleWarning cascade.
- **RasterParser** — orchestrator mirroring DXFParser/PDFParser interface; `extract_walls(catalog_builder, dimensions)` returns `(walls, metadata, catalog)`.
- **YOLOv8 integration** (`cv/detection_service.py`) — consumes models via registry.
- **Gemini Vision scale detection** (`cv/floor_plan_service.py`) — consumes models via registry.

### YOLO Model Storage & Registry (Sprint 0 pre-work)
- GCS bucket `gs://construction-ai-models/` with object versioning + 90-day lifecycle.
- `LiveModelRegistry` with hot-swap (serialized background loading, atomic cutover).
- `ml/models.yaml` manifest — single source of truth for 3 models, 5 versions.
- `ml/publish.py` CLI.
- API endpoints: `GET /api/models/list`, `GET /api/models/status`, `POST /api/models/{name}/activate`, `GET /api/models/history`.
- 53 tests, 100% coverage.

### Structural Analysis
- Euler-Bernoulli beam solver (finite-difference method) — verified 0.001% error vs analytical at N=200.
- C++ benchmark port in `benchmarks/structural/` — 1.1 ms vs Python 4.1 ms (~3.6x).
- Grid convergence: p_hat ≈ 2.000 across N=10,20,40,80,160 (2nd-order confirmed).
- **Not yet wired** into takeoff pipeline (Backlog 3.2, Header Sizing).

### Infrastructure (LIVE)
- **Cloud Run** backend at `https://construction-ai-backend-542888988741.us-east4.run.app` (revision `00007-pk6`, 4 GiB / 2 CPU).
- **Neo4j Community Edition** self-hosted on GCE `e2-small` VM in `us-east4-a`, reserved internal IP `10.150.0.2`, reached via Serverless VPC Access connector.
- **Artifact Registry** for container images.
- **Secret Manager** for `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (Terraform-managed versions).
- **Workload Identity Federation** pool + provider; CI deployer SA (least-privilege: AR writer + run.developer + iam.serviceAccountUser only).
- **CI**: GitHub Actions pytest with coverage on PR/master.
- **CD**: WIF-auth build/push to AR → deploy Cloud Run → smoke-test live URL. CD run #27512255933 was the first fully green end-to-end.
- **Cost**: ≈$28/mo all-in on `vt-gcp-00042` (Cloud Run scales to zero when idle).

### Test Coverage (2026-07-04)
| Suite | Count | Coverage |
|---|---|---|
| Total tests | 355 passing + 8 testcontainer-gated skips | — |
| Sprint 2 (KG) | ~30 | 100% on `app.core.kg` |
| Sprint 3 (CV) | 82 | 100% on `image_preprocessor`, `coordinate_converter`, `wall_line_extractor`, `scale_detector`, `raster_parser` |
| Sprint 4 (OCR + catalog + wiring) | ~150 | 100% on `dimension_parser`, `dimension_extractor`, `easyocr_reader`, `spatial_association`, `catalog_builder`, `catalog_store`, `validation_summary`, `raster_takeoff`, `pdf_takeoff`, catalog API |
| Sprint 4f (pdf_parser rewrite) | 61 + 1 e2e | 100% on `parsers.pdf_parser` (179 stmts), 100% on `integration/test_phase1_e2e.py` |
| Sprint 5 (e2e integration) | 25 surface + 8 previous | 100% on `integration/test_phase1_e2e.py` |
| Testcontainer skips | 8 | KG integration tests gated on Docker availability |

## Feature Specification Status

| Feature | Spec File | Status |
|---------|-----------|--------|
| Sprint 0 memory-bank refresh | `sprint-0-memory-bank-refresh.md` | VERIFIED |
| Sprint 1a VVUQ citations | `sprint-1a-vvuq-structural-mechanics-citations.md` | VERIFIED |
| Sprint 1b VVUQ slides | `sprint-1b-vvuq-presentation-slides.md` | VERIFIED |
| Sprint 1c VVUQ final review | `sprint-1c-vvuq-paper-final-review.md` | VERIFIED (VVUQ Phase 3 CLOSED) |
| Sprint 2a Neo4j KG foundation | `sprint-2a-neo4j-kg-foundation.md` | VERIFIED |
| Sprint 2b CI/CD + Terraform GCP | `sprint-2b-cicd-bootstrap-gcp.md` | VERIFIED |
| Sprint 2c live deploy + smoke | `sprint-2c-aura-deploy-smoke-test.md` | VERIFIED |
| Sprint 3a CV foundation | `sprint-3a-cv-pipeline-foundation.md` | VERIFIED |
| Sprint 3b raster extraction | `sprint-3b-raster-wall-extraction-api.md` | VERIFIED |
| Sprint 4a OCR parser + extractor | `sprint-4a-ocr-dimension-parser-extractor.md` | VERIFIED |
| Sprint 4b object catalog | `sprint-4b-object-catalog-foundation.md` | VERIFIED |
| Sprint 4c catalog integration | `sprint-4c-catalog-integration.md` | VERIFIED |
| Sprint 4d takeoff wiring | `sprint-4d-takeoff-wiring.md` | VERIFIED |
| Sprint 4e scanned-PDF dispatch | `sprint-4e-scanned-pdf-dispatch.md` | VERIFIED |
| Sprint 4f PDF parser fix | `sprint-4f-pdf-vector-parser-unit-fix.md` | VERIFIED |
| Sprint 5 Phase 1 e2e | `sprint-5-phase1-integration-smoke-test.md` | VERIFIED |
| Neo4j Setup (superseded by 2a-c) | `neo4j-setup.md` | SPECIFIED (superseded) |
| Raster Support (superseded by 3a-b) | `raster-scanned-drawing-support.md` | SPECIFIED (superseded) |
| OCR Extraction (superseded by 4a-f) | `ocr-dimension-extraction.md` | SPECIFIED (superseded) |
| YOLO Model Storage | `yolo-model-storage.md` | VERIFIED |

Full backlog: `llm/features/BACKLOG.md`.

## What Remains to Build

### Immediate (queued Phase 1 closeout)
- [ ] Sprint 6 — KG-latency benchmark (<100 ms). Closes Phase 1 §8 criterion 3. Needs a decision on Neo4j-in-CI (extend testcontainers or spin an ephemeral GCE instance).
- [ ] User hand-counted plans → gated fixtures in `references.json` → activate Sprint 5's ≤10% wall-LF gate.

### Near-Term (backlog, needs specification)
- [ ] Backlog 3.2 Header Sizing — wire `beam_solver.py` into `lumber_calculator.py` for opening-header assessment. Beam solver exists and is verified; just needs pipeline plumbing.
- [ ] Backlog 4.1 Cut List Optimization (OR-Tools) — high user value; OR-Tools is a declared dependency but the `optimization/` directory is still empty.
- [ ] Backlog 8.1 IRC Compliance Engine — codify IRC residential checks (stud spacing, bearing, header sizing, fire separation, egress). Depends on KG rules.
- [ ] Multi-page scale detection — currently only page 0's scale is auto-detected; downstream pages inherit it.
- [ ] Ratio-format scale strings (`1:48`, `1:100`) — separate sprint if any real-world plans use them.

### Medium-Term
- [ ] Backlog 6.x LLM agent framework (5-6 specialized agents from proposal). `core/llm/` is empty placeholder.
- [ ] Backlog 3.3 Complete framing package — joists, rafters, blocking, corners.
- [ ] Backlog 3.4 Concrete & foundation.
- [ ] Backlog 11.2 Async task processing (Celery + Redis) — commented out in docker-compose.yml.

### Long-Term
- [ ] Backlog 9.2 CAD output generation (labeled DXF/DWG/SVG) — `cad_generation/` empty placeholder.
- [ ] Backlog 10.5 Authentication + Backlog 10.6 project management.
- [ ] Backlog 10.3 Three.js 3D visualization — R3F is in frontend deps.
- [ ] Multi-story buildings.

## Known Issues and Tech Debt

- `backend/app/core/llm/`, `optimization/`, `cad_generation/` are empty placeholder directories.
- `ARCHITECTURE.md` at project root is empty (0 bytes).
- Multiple overlapping documentation files at project root (QUICK_SETUP.md, QUICKSTART.md, RUN_GUIDE.md, etc.).
- `memory-bank/` (root) and `llm/memory_bank/` are duplicated — `llm/memory_bank/` is authoritative.
- Legacy YOLO model paths in `config.py` (deprecated, kept for fallback).
- `backend/app/core/cv/best.pt` (50MB) still in git history — uploaded to GCS but not yet removed from tracking.
- Phase 1 §8 criterion 1 (BOM accuracy >90%) blocked on user's hand-counted plan uploads.

## Milestones

| Milestone | Description | Status | Date |
|-----------|-------------|--------|------|
| M0 | Documentation infrastructure | Complete | 2026-02-03 |
| M0.5 | Structural beam solver | Complete | 2026-03-06 |
| M0.7 | Feature backlog + 3 specs | Complete | 2026-04-01 |
| M0.8 | Model registry | Complete | 2026-04-03 |
| M1 | Foundation (Neo4j + CI/CD live on GCP) | Complete | 2026-06-14 |
| M2 | Raster + OCR + catalog e2e wired | Complete | 2026-06-14 |
| M2.5 | Multi-page + scanned-PDF dispatch | Complete | 2026-06-20 |
| M3 | Phase 1 e2e integration smoke test | Complete | 2026-06-25 |
| M3.5 | PDF vector-parser robust on real plans | Complete | 2026-07-08 |
| M4 | KG-latency benchmark (Phase 1 §8 crit 3) | Not started | — |
| M5 | Agent framework | Not started | — |
| M6 | Full MVP end-to-end (all Phase 1 criteria green) | Blocked on user fixtures + M4 | — |
