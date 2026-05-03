# Progress

Last updated: 2026-04-03

## What Is Built and Working

### Plan Parsing Pipeline (Phase 1 MVP)
- DXF parsing via ezdxf — extracts wall geometry as LINE/LWPOLYLINE entities
- DWG→DXF auto-conversion via LibreDWG
- PDF vector extraction via PyMuPDF
- Wall element extraction with start/end coordinates and length calculation

### Material Takeoff Calculation
- Stud calculation with configurable spacing (12", 16", 24" O.C.)
- Top and bottom plate calculation (single or double top plate)
- Lumber specification database (nominal vs actual dimensions for 2x4 through 2x12)
- JSON-formatted material list output

### Web Interface
- React frontend with file upload (DWG, DXF, PDF)
- Parameter configuration (wall height, stud spacing)
- Material takeoff results display
- Object detection results page
- Floor plan analysis page with scale calibration

### Computer Vision (Partial)
- YOLOv8 integration (`backend/app/core/cv/detection_service.py`)
- Gemini Vision scale detection (`backend/app/core/cv/floor_plan_service.py`)
- 3 trained YOLO models (boundary, objects, detection) stored in GCS

### YOLO Model Storage & Registry (VERIFIED — 2026-04-03)
- GCS bucket `gs://construction-ai-models/` with object versioning + 90-day lifecycle
- `LiveModelRegistry` with hot-swap (serialized background loading, atomic cutover)
- `ml/models.yaml` manifest — single source of truth for 3 models, 5 versions
- `ml/publish.py` CLI — upload + capture generation + update manifest in one command
- Generation pinning ensures exact model version reproducibility
- API endpoints: `GET /api/models/list`, `GET /api/models/status`, `POST /api/models/{name}/activate`, `GET /api/models/history`
- Service account `model-registry@vt-gcp-00042.iam.gserviceaccount.com`
- Terraform infrastructure in `infra/main.tf`
- 53 tests, 100% coverage

### Structural Analysis
- Euler-Bernoulli beam solver (finite-difference method) for header/beam assessment
- C++ benchmark port in `benchmarks/structural/`

### Infrastructure
- Docker Compose stack (PostgreSQL, FastAPI, React)
- SQLAlchemy database setup with SQLite fallback
- GCS bucket for model storage (Terraform-managed)

## Feature Specification Status

| Feature | Spec File | Status |
|---------|-----------|--------|
| Raster/Scanned Drawing Support | `raster-scanned-drawing-support.md` | SPECIFIED |
| OCR Dimension Extraction | `ocr-dimension-extraction.md` | SPECIFIED |
| YOLO Model Storage | `yolo-model-storage.md` | VERIFIED |
| Neo4j Setup | `neo4j-setup.md` | Needs update |

Full backlog: `llm/features/BACKLOG.md` (45+ features across 11 domains)

## What Remains to Build

### Ready for Implementation (specs written)
- [ ] Raster/scanned drawing support — YOLO-constrained Hough line extraction, scale plausibility
- [ ] OCR dimension extraction — parse annotations, build object catalog, validate geometry

### Near-Term (needs specification)
- [ ] Cut list optimization (OR-Tools) — high user value, declared dependency
- [ ] Header sizing — connect beam_solver.py to takeoff pipeline
- [ ] Neo4j Knowledge Graph setup

### Medium-Term
- [ ] LLM agent framework (5 specialized agents from proposal)
- [ ] Code compliance checking (IRC residential)
- [ ] Celery/Redis async task processing
- [ ] Complete framing package (joists, rafters, blocking)

### Long-Term
- [ ] Build instruction generation with provenance
- [ ] CAD output generation (labeled DXF/DWG/SVG)
- [ ] Multi-story building support
- [ ] User authentication and project management
- [ ] 3D visualization (Three.js/R3F already in frontend deps)

## Known Issues and Tech Debt

- `backend/app/core/llm/`, `optimization/`, `cad_generation/` are empty placeholder directories
- `ARCHITECTURE.md` at project root is empty (0 bytes)
- Multiple overlapping documentation files at project root (QUICK_SETUP.md, QUICKSTART.md, RUN_GUIDE.md, etc.)
- `memory-bank/` (root) and `llm/memory_bank/` are duplicated — `llm/memory_bank/` is authoritative
- Legacy YOLO model paths in config.py (deprecated, kept for fallback)
- `backend/app/core/cv/best.pt` (50MB) still in git history — uploaded to GCS but not yet removed from tracking
- No CI/CD pipeline configured

## Milestones

| Milestone | Description | Status | Date |
|-----------|-------------|--------|------|
| M0 | Documentation infrastructure | Complete | 2026-02-03 |
| M0.5 | Structural beam solver | Complete | 2026-03-06 |
| M0.7 | Feature backlog + 3 specs | Complete | 2026-04-01 |
| M0.8 | Model registry (first verified feature) | Complete | 2026-04-03 |
| M1 | Foundation (Neo4j, API review) | Not started | - |
| M2 | Raster + OCR parsing | Ready to start | - |
| M3 | Agent framework | Not started | - |
| M4 | MVP end-to-end | Not started | - |
