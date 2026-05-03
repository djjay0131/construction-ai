# System Patterns

## High-Level Architecture

Monolithic application with a React SPA frontend and a Python FastAPI backend, deployed via Docker Compose. The backend handles file parsing, geometry extraction, material calculation, computer vision, and model management. The frontend provides file upload, parameter configuration, and results display.

```
Browser (React SPA)
    │
    ▼
FastAPI Backend (/api/*)
    ├── /api/upload     → File upload and storage
    ├── /api/takeoff    → Material takeoff processing
    ├── /api/detection  → YOLOv8 object detection
    ├── /api/floor-plan → Floor plan analysis (Gemini Vision)
    └── /api/models     → Model registry management (hot-swap, status)
    │
    ▼
PostgreSQL / SQLite (project metadata)
GCS (model weight storage)
```

## Directory Structure

```
construction-ai/
├── backend/app/
│   ├── main.py                    # FastAPI app entry point, router registration
│   ├── api/                       # Route handlers
│   │   ├── upload.py              # File upload
│   │   ├── takeoff.py             # Material takeoff processing
│   │   ├── detection.py           # YOLOv8 object detection
│   │   ├── floor_plan.py          # Floor plan analysis
│   │   └── models.py              # Model registry API (list, status, activate, history)
│   ├── core/
│   │   ├── config.py              # Application settings (pydantic-settings)
│   │   ├── parsers/               # DXF/DWG/PDF file parsers
│   │   │   ├── dxf_parser.py      # ezdxf-based DXF parsing, WallElement extraction
│   │   │   ├── dwg_converter.py   # LibreDWG DWG→DXF conversion
│   │   │   └── pdf_parser.py      # PyMuPDF vector extraction
│   │   ├── extraction/            # Material calculation
│   │   │   └── lumber_calculator.py  # Stud/plate quantity calculation
│   │   ├── cv/                    # Computer vision services
│   │   │   ├── detection_service.py  # YOLOv8 inference (uses model registry)
│   │   │   ├── floor_plan_service.py # Gemini Vision scale detection (uses model registry)
│   │   │   └── helper.py
│   │   ├── ml/                    # Model management
│   │   │   ├── model_registry.py  # LiveModelRegistry: resolve, load, hot-swap
│   │   │   └── model_store.py     # GCS upload/download with generation pinning
│   │   ├── structural/            # Structural analysis
│   │   │   └── beam_solver.py     # Euler-Bernoulli FD beam solver
│   │   ├── llm/                   # LLM integration (empty, planned)
│   │   ├── optimization/          # Cut optimization (empty, planned)
│   │   └── cad_generation/        # CAD output (empty, planned)
│   ├── schemas/                   # Pydantic request/response models
│   │   ├── material.py            # MaterialTakeoff, LumberMaterialItem
│   │   ├── detection.py           # DetectionResult, DetectedObject
│   │   ├── floor_plan.py          # PDFAnalysisResult, ScaleInfo
│   │   └── model.py               # ModelListResponse, SwapRequest, SwapEventResponse
│   ├── models/                    # SQLAlchemy ORM models
│   ├── db/                        # Database initialization
│   └── utils/
├── backend/tests/                 # pytest test suite (53 tests)
│   ├── test_model_registry.py
│   ├── test_model_store.py
│   ├── test_model_api.py
│   └── test_publish.py
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
The core data flow is a sequential pipeline:
1. **Parse**: `parsers/dxf_parser.py` reads DXF entities → produces `WallElement` dataclasses
2. **Extract**: `extraction/lumber_calculator.py` takes `WallElement` list → calculates stud counts, plate lengths
3. **Output**: Returns `LumberMaterialItem` Pydantic models via API

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
User uploads DWG/DXF/PDF
    → backend/app/api/upload.py stores file, returns drawing_id
    → backend/app/api/takeoff.py called with drawing_id + params
        → parsers/dxf_parser.py (or pdf_parser.py) extracts WallElements
        → extraction/lumber_calculator.py computes stud counts + plate LF
    → JSON response with material items returned to frontend
    → frontend/src/components/TakeoffResults.tsx renders results
```

## Naming Conventions

- **Python**: snake_case for functions/variables, PascalCase for classes, modules named by domain
- **TypeScript**: camelCase for variables, PascalCase for components/types
- **API routes**: kebab-case paths (`/api/floor-plan`), REST-style resource naming
- **Files**: snake_case for Python, PascalCase for React components
- **Feature specs**: kebab-case filenames in `llm/features/`
- **Test files**: `test_<module>.py` with `test_<behavior>_<condition>` method names
