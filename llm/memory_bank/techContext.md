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
| Graph DB | Neo4j Community Edition | 5.x, self-hosted on GCE `e2-small` |
| Container runtime | Cloud Run v2 | 4 GiB / 2 CPU / scale-to-zero |

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

### Computer Vision (Sprint 3, wired end-to-end)
- **ultralytics 8.4.21** (YOLOv8) — Object detection for construction elements
- **opencv-python 4.8.1.78** — Image processing pipeline (skew rejection, CLAHE, Hough)
- **easyocr 1.7.0** — OCR for dimension extraction (Sprint 4a lazy-init wrapper)
- **google-genai >=0.2.0** — Gemini Vision API for scale detection (scaffolded)

### Knowledge Graph (Sprint 2)
- **neo4j >=5.0** — Bolt driver for Cypher queries
- **testcontainers[neo4j]** — ephemeral Neo4j container for integration tests (8 tests gated on Docker availability)

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

### Cloud (GCP — project `vt-gcp-00042`) — LIVE
- **Cloud Run v2 service** `construction-ai-backend` in `us-east4`
  - 4 GiB / 2 CPU / scale-to-zero
  - Public URL: <https://construction-ai-backend-542888988741.us-east4.run.app>
  - Container image pushed to Artifact Registry
- **Artifact Registry** repo for backend container images
- **Compute Engine** `e2-small` VM in `us-east4-a` hosting Neo4j Community Edition
  - Reserved internal IP: `10.150.0.2`
  - Dedicated runtime SA, systemd-managed
- **Serverless VPC Access connector** — Cloud Run → Neo4j VM over private VPC
- **Secret Manager** — 3 secrets (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`), Terraform-managed versions
- **Workload Identity Federation** pool + provider for GitHub Actions
- **CI deployer SA** with least-privilege IAM (AR writer + run.developer + iam.serviceAccountUser)
- **GCS bucket** `gs://construction-ai-models/` — YOLO model weight storage
  - Object versioning enabled
  - Lifecycle policy: delete noncurrent after 90 days, keep 1 previous
- **Service account** `model-registry@vt-gcp-00042.iam.gserviceaccount.com` — objectAdmin on models bucket
- **Terraform** manages everything above in `infra/main.tf` (see `infra/README.md` for the operator runbook)
- **Est. cost**: ≈$28/mo all-in

### CI/CD
- **CI** (`.github/workflows/ci.yml`) — pytest with coverage on every PR and push to master. Coverage XML uploaded as artifact.
- **CD** (`.github/workflows/cd.yml`) — on push to master: WIF auth → build → push to AR → `gcloud run deploy` → smoke-test live URL. Fails CD if new revision isn't `ready` or smoke-test returns non-200.
- First fully green end-to-end CD run: #27512255933 (2026-06-14).

## Technical Constraints

- DWG files require LibreDWG system dependency for conversion
- PDF parsing handles vector + scanned (per-page dispatch after Sprint 4e); PDF scale detection is single-page-only (page 0)
- Skewed drawings are rejected (no deskew correction — design decision from specs)
- No authentication or multi-tenancy
- Backend uses synchronous processing (no Celery workers yet)
- YOLO models require GCS credentials to download on first startup (~150MB total)
- Neo4j is optional for local dev (graceful degradation to `kg_status=degraded`); required in prod
