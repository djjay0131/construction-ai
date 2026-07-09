# System Patterns

## High-Level Architecture

Monolithic application with a React SPA frontend and a Python FastAPI backend, deployed via Docker Compose. The backend handles file parsing, geometry extraction, material calculation, computer vision, and model management. The frontend provides file upload, parameter configuration, and results display.

```
Browser (React SPA)
    │
    ▼
FastAPI Backend (Cloud Run — /api/*)
    ├── /api/upload         → File upload and storage
    ├── /api/takeoff        → Material takeoff (DXF/vector-PDF/scanned-PDF/JPG/PNG)
    ├── /api/detection      → YOLOv8 object detection
    ├── /api/floor-plan     → Floor plan analysis (Gemini Vision)
    ├── /api/models         → Model registry management (hot-swap, status)
    ├── /api/catalog/{id}   → Object catalog JSON
    └── /api/health/kg      → KG readiness + lumber-specs-loaded (always 200)
    │
    ├──▶ Neo4j (self-hosted on GCE, reached via VPC connector)
    │       └── Lumber specs, IRC rules, provenance edges
    │
    ├──▶ PostgreSQL / SQLite (project metadata)
    └──▶ GCS (model weight storage, gs://construction-ai-models/)
```

## Directory Structure

```
construction-ai/
├── backend/app/
│   ├── main.py                    # FastAPI app entry point, router registration
│   ├── api/                       # Route handlers
│   │   ├── upload.py              # File upload
│   │   ├── takeoff.py             # Material takeoff processing (dispatches by ext)
│   │   ├── detection.py           # YOLOv8 object detection
│   │   ├── floor_plan.py          # Floor plan analysis
│   │   ├── models.py              # Model registry API (list, status, activate, history)
│   │   ├── catalog.py             # GET /api/catalog/{takeoff_id} (Sprint 4c)
│   │   └── health.py              # /api/health/kg (Sprint 2c) — always 200
│   ├── core/
│   │   ├── config.py              # Application settings (pydantic-settings)
│   │   ├── parsers/               # DXF/DWG/PDF/raster file parsers
│   │   │   ├── dxf_parser.py      # ezdxf-based DXF parsing, WallElement extraction
│   │   │   ├── dwg_converter.py   # LibreDWG DWG→DXF conversion
│   │   │   ├── pdf_parser.py      # PyMuPDF vector extraction — 5 path-item shapes, scale detection cascade (Sprint 4f)
│   │   │   └── raster_parser.py   # Sprint 3b orchestrator; extract_walls returns (walls, meta, catalog)
│   │   ├── cv/                    # Computer vision
│   │   │   ├── detection_service.py    # YOLOv8 inference (uses model registry)
│   │   │   ├── floor_plan_service.py   # Gemini Vision scale detection
│   │   │   ├── image_preprocessor.py   # Skew reject + CLAHE + Gaussian (Sprint 3a)
│   │   │   ├── coordinate_converter.py # px→inch → WallElement (Sprint 3a)
│   │   │   ├── wall_line_extractor.py  # YOLO-constrained Hough (Sprint 3b, Protocol DI)
│   │   │   ├── scale_detector.py       # reference > manual > ScaleWarning (Sprint 3b)
│   │   │   ├── dimension_parser.py     # regex ft-in/frac/mm/m (Sprint 4a)
│   │   │   ├── dimension_extractor.py  # orchestrates OcrReader Protocol (Sprint 4a)
│   │   │   └── easyocr_reader.py       # lazy-init EasyOCR wrapper (Sprint 4c)
│   │   ├── catalog/               # Sprint 4b — object catalog graph
│   │   │   ├── spatial_association.py  # dim ↔ node pairing by centroid dist
│   │   │   ├── catalog_builder.py      # CONNECTS_TO + CONTAINS edges, OCR validation
│   │   │   ├── catalog_store.py        # JSON save/load
│   │   │   └── validation_summary.py   # confirmed/minor/mismatch counts
│   │   ├── kg/                    # Sprint 2a — Neo4j client
│   │   │   ├── client.py               # Bolt driver + graceful degradation
│   │   │   ├── provenance.py           # cite_rule_for(item)
│   │   │   └── loader.py               # Seed lumber specs + IRC rules
│   │   ├── extraction/            # Material calculation
│   │   │   └── lumber_calculator.py    # Stud/plate calc + KG rule citations + source_walls
│   │   ├── raster_takeoff.py      # Sprint 4d — RasterParser + DimExtractor + CatalogBuilder + Store
│   │   ├── pdf_takeoff.py         # Sprint 4e — multi-page vector-first, raster fallback, page tagging
│   │   ├── ml/                    # Model management
│   │   │   ├── model_registry.py  # LiveModelRegistry: resolve, load, hot-swap
│   │   │   └── model_store.py     # GCS upload/download with generation pinning
│   │   ├── structural/            # Structural analysis
│   │   │   └── beam_solver.py     # Euler-Bernoulli FD beam solver (verified)
│   │   ├── llm/                   # LLM integration (empty, planned)
│   │   ├── optimization/          # Cut optimization (empty, planned)
│   │   └── cad_generation/        # CAD output (empty, planned)
│   ├── schemas/                   # Pydantic request/response models
│   │   ├── material.py            # MaterialTakeoff, LumberMaterialItem (source_walls, rule_citations)
│   │   ├── detection.py           # DetectionResult, DetectedObject
│   │   ├── floor_plan.py          # PDFAnalysisResult, ScaleInfo
│   │   └── model.py               # ModelListResponse, SwapRequest, SwapEventResponse
│   ├── models/                    # SQLAlchemy ORM models
│   ├── db/                        # Database initialization
│   └── utils/
├── backend/tests/                 # pytest suite — 355 pass + 8 testcontainer-gated skips
│   ├── integration/
│   │   └── test_phase1_e2e.py     # Sprint 5 — drives every fixture through takeoff
│   ├── fixtures/phase1/           # references.json + fixture files
│   ├── test_model_registry.py     # Sprint 0 pre-work
│   ├── test_kg_*.py               # Sprint 2
│   ├── test_image_preprocessor.py # Sprint 3a
│   ├── test_wall_line_extractor.py, test_scale_detector.py, test_raster_parser.py  # Sprint 3b
│   ├── test_dimension_*, test_catalog_*, test_easyocr_reader.py, test_validation_summary.py  # Sprint 4a-c
│   ├── test_raster_takeoff.py, test_pdf_takeoff.py  # Sprint 4d/4e
│   └── test_pdf_parser.py         # Sprint 4f — 61 tests, 100% cov on 179 stmts
├── frontend/src/                  # React SPA
├── ml/                            # Model registry
│   ├── models.yaml                # Model manifest (source of truth, checked into git)
│   ├── models/                    # Local model cache (gitignored, downloaded from GCS)
│   └── publish.py                 # CLI: upload model + update manifest
├── infra/                         # Terraform infrastructure
│   └── main.tf                    # GCS bucket + service account + IAM
├── llm/                           # Feature management
│   ├── features/                  # Feature specs (BACKLOG.md + individual specs)
│   └── memory_bank/               # Project context documentation (authoritative)
├── memory-bank/                   # Legacy docs (synced from proposal repo, superseded by llm/memory_bank/)
├── datascience/                   # ML notebooks and training data
├── benchmarks/structural/         # C++ beam solver port for benchmarking
├── construction/                  # Sprint planning, design documents
└── files/                         # Ground truth data, uploaded files
```

## Key Design Patterns

### Parser → Extraction → Output Pipeline
The core data flow is a sequential pipeline. Dispatch on file extension:
1. **Parse**:
   - `.dxf` / `.dwg` → `parsers/dxf_parser.py` reads entities → `WallElement`
   - `.pdf` → `core/pdf_takeoff.py` iterates pages; per-page vector-first via `parsers/pdf_parser.py`, raster fallback via `parsers/raster_parser.py`. Walls tagged `metadata["source"] ∈ {pdf_vector, pdf_raster}` and `metadata["page"]`.
   - `.jpg` / `.png` → `core/raster_takeoff.py` runs `RasterParser` + `DimensionExtractor` + `ObjectCatalogBuilder` + `CatalogStore` in one shot.
2. **Extract**: `extraction/lumber_calculator.py` takes `WallElement` list → calculates stud counts, plate lengths. If a KG client is injected, populates `rule_citations` (IRC R602.3.x etc.) and `source_walls` (page-tagged wall IDs) on every line item.
3. **Output**: Returns `LumberMaterialItem` Pydantic models via API. Catalog persists to disk under a canonical path per `takeoff_id`; retrievable via `GET /api/catalog/{takeoff_id}`.

### Singleton Service Pattern
Long-lived service instances are created as module-level singletons with `get_*()` factory functions:
- `get_detection_service()` — DetectionService
- `get_floor_plan_service()` — FloorPlanAnalysisService
- `get_model_registry()` — LiveModelRegistry

These are injected into FastAPI routes via `Depends()`.

### Model Registry Pattern
YOLO models are managed through a centralized registry:
1. `ml/models.yaml` manifest declares model names, versions, GCS paths, generation pins
2. `LiveModelRegistry` resolves names → downloads from GCS → caches locally → loads into memory
3. Hot-swap via background thread (serialized, max_workers=1) with atomic cutover under RLock
4. CV services (`DetectionService`, `FloorPlanAnalysisService`) consume models via `registry.get_loaded_model(name)` with legacy path fallback

### Dataclass + Pydantic Schema Separation
- Internal domain objects use Python `@dataclass` (e.g., `WallElement`, `BeamGeometry`, `FramingConfig`, `ModelInfo`, `SwapEvent`)
- API boundaries use Pydantic models (e.g., `LumberMaterialItem`, `SwapRequest`, `ModelListResponse`)

### Router-per-Domain API Organization
Each API domain gets its own router module in `backend/app/api/`:
- `upload.py` → `/api/upload/*`
- `takeoff.py` → `/api/takeoff/*`
- `detection.py` → `/api/detection/*`
- `floor_plan.py` → `/api/floor-plan/*`
- `models.py` → `/api/models/*`

Routers are registered in `main.py` via `app.include_router()`.

### Feature Specification Workflow
Features follow a specify → implement → verify lifecycle:
1. **Specify**: `/constellize:feature:specify` — adversarial interview, sample implementation, dual-persona review → `llm/features/<name>.md` with status SPECIFIED
2. **Implement**: `/constellize:feature:implement` — star-gap-generate, test-first, adversarial test review → status IMPLEMENTED
3. **Verify**: `/constellize:feature:verify` — 4 quality gates (tests, health check, deployment, maintainability) → status VERIFIED

## Primary Use Case Data Flow

```
User uploads DWG/DXF/PDF/JPG/PNG
    → backend/app/api/upload.py stores file, returns drawing_id
    → backend/app/api/takeoff.py called with drawing_id + params
        → dispatch by extension:
            .dxf/.dwg → parsers/dxf_parser.py
            .pdf      → core/pdf_takeoff.py (per-page vector-first, raster fallback)
            .jpg/.png → core/raster_takeoff.py (raster + OCR + catalog)
        → extraction/lumber_calculator.py computes stud counts + plate LF
            → if KG client present: cite_rule_for(item) → rule_citations
            → source_walls populated from page-tagged wall IDs
        → catalog persisted at canonical path per takeoff_id
    → JSON response with material items returned to frontend
    → frontend/src/components/TakeoffResults.tsx renders results

GET /api/catalog/{takeoff_id} → catalog JSON (Sprint 4c)
GET /api/health/kg → {kg_status, lumber_specs_loaded} (Sprint 2c)
```

### Test Pyramid (Phase 1 e2e)

`backend/tests/integration/test_phase1_e2e.py` (Sprint 5) drives every
fixture in `backend/tests/fixtures/phase1/references.json` through
dispatch by `kind` (dxf/pdf). Each fixture declares:
- `role: "smoke"` or `role: "gated"` (gated ⇒ ≤10% wall-LF error)
- `total_wall_lf` (nullable — null means smoke-only)
- `line_items` reference counts
- Provenance + license note

Currently active: `dxf_smoketest_4wall` (64 LF, hand-built via ezdxf) +
`vector_pdf_vermont` (CC-BY-SA WikihouseUS, activated by Sprint 4f).

## Naming Conventions

- **Python**: snake_case for functions/variables, PascalCase for classes, modules named by domain
- **TypeScript**: camelCase for variables, PascalCase for components/types
- **API routes**: kebab-case paths (`/api/floor-plan`), REST-style resource naming
- **Files**: snake_case for Python, PascalCase for React components
- **Feature specs**: kebab-case filenames in `llm/features/`
- **Test files**: `test_<module>.py` with `test_<behavior>_<condition>` method names
