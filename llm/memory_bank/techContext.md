# Technical Context

## Languages and Frameworks

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend | Python + FastAPI | Python 3.11+, FastAPI 0.104.1 |
| Frontend | React + TypeScript | React 18.2, TS 5.2 |
| Build tool | Vite | 5.0.8 |
| Styling | TailwindCSS | 3.3.6 |
| State management | Zustand | 4.4.7 |
| Data fetching | @tanstack/react-query | 5.12.2 |
| 3D visualization | Three.js + React Three Fiber | three 0.159, r3f 8.15 |
| Database | SQLAlchemy + PostgreSQL/SQLite | SQLAlchemy 2.0.23 |
| Containerization | Docker + Docker Compose | compose 3.8 |
| Infrastructure | Terraform | 1.5.7 |
| Cloud | Google Cloud Platform | Project: vt-gcp-00042 |

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose (for full stack)
- PostgreSQL (optional; SQLite works for dev)
- `GOOGLE_APPLICATION_CREDENTIALS` env var pointing to GCS service account key (for model registry)

### Quick Start (Docker)

```bash
docker-compose up --build
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/api/docs
```

### Manual Start

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export GOOGLE_APPLICATION_CREDENTIALS=../infra/model-registry-key.json
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
python -m pytest tests/ -v --cov
```

### Scripts

- `./launch.sh` — Start all services
- `backend/start_server.sh` — Start backend with checks
- `frontend/start_dev.sh` — Start frontend dev server

## Key Dependencies and Rationale

### CAD/PDF Parsing (Core)
- **ezdxf 1.1.3** — Native DXF parsing; extracts wall geometry as LINE/LWPOLYLINE entities
- **PyMuPDF 1.23.8** — PDF vector extraction; reads paths/lines from vector-based architectural PDFs
- **LibreDWG** (system dependency) — Converts proprietary DWG to DXF format

### Computer Vision (Phase 2, partially implemented)
- **ultralytics 8.4.21** (YOLOv8) — Object detection for construction elements
- **opencv-python 4.8.1.78** — Image processing pipeline
- **easyocr 1.7.0** — OCR for dimension extraction from drawings
- **google-genai >=0.2.0** — Gemini Vision API for scale detection

### ML Framework
- **torch 2.10.0 + torchvision 0.25.0** — Backend for YOLOv8 and future ML models

### Model Storage
- **google-cloud-storage >=2.14.0** — GCS client for model download/upload with generation pinning
- **pyyaml >=6.0.1** — Manifest parsing for model registry

### Structural Analysis
- **numpy + scipy** — Finite-difference Euler-Bernoulli beam solver

### Testing
- **pytest 7.4.3** — Test framework
- **pytest-asyncio 0.21.1** — Async test support
- **pytest-cov** — Coverage reporting
- **httpx 0.25.2** — Async HTTP client for API testing

## Infrastructure

### Local
- **Docker Compose** orchestrates PostgreSQL 15, FastAPI backend, React frontend
- **PostgreSQL** for production; SQLite for local development
- **Redis + Celery** planned but commented out in docker-compose.yml

### Cloud (GCP — project `vt-gcp-00042`)
- **GCS bucket** `gs://construction-ai-models/` — YOLO model weight storage
  - Object versioning enabled
  - Lifecycle policy: delete noncurrent after 90 days, keep 1 previous
  - Generation pinning for exact version reproducibility
- **Service account** `model-registry@vt-gcp-00042.iam.gserviceaccount.com` — objectAdmin on models bucket
- **Terraform** manages GCS + IAM in `infra/main.tf`

### Not Yet Deployed
- No CI/CD pipeline
- No Neo4j instance
- No production deployment (cloud VMs, GKE, etc.)

## Technical Constraints

- DWG files require LibreDWG system dependency for conversion
- PDF parsing only works with vector-based drawings (raster support specified but not yet built)
- Skewed drawings are rejected (no deskew correction — design decision from specs)
- No authentication or multi-tenancy
- Backend uses synchronous processing (no Celery workers yet)
- YOLO models require GCS credentials to download on first startup (~150MB total)
