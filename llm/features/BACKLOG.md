# Feature Backlog

All planned capabilities for Construction.AI, consolidated from the proposal repo, memory-bank vision docs, and README roadmap. Each item is a candidate for detailed specification via `constellize:feature:specify`.

Status key: **DONE** | **PARTIAL** | **PLANNED** | **VISION**

---

## 1. Plan Parsing & Extraction

### 1.1 DXF/DWG Parsing — **DONE**
Parse DXF files via ezdxf, auto-convert DWG via LibreDWG. Extract wall geometry as LINE/LWPOLYLINE entities with start/end coordinates and length.
- Files: `backend/app/core/parsers/dxf_parser.py`, `dwg_converter.py`

### 1.2 PDF Vector Extraction — **DONE**
Extract wall geometry from vector-based PDF floor plans using PyMuPDF path extraction. Sprint 4f rewrite handles 5 path-item shapes (`m`, `l` both forms, `re`, `qu`, `c`) with scale detection cascade + 1-inch minimum wall length filter.
- Files: `backend/app/core/parsers/pdf_parser.py`

### 1.3 Raster/Scanned Drawing Support — **DONE** (Sprints 3a, 3b, 4e)
Scanned drawings (JPG, PNG, scanned PDF pages) via full CV pipeline: skew reject → CLAHE preprocess → YOLO-constrained Hough line extraction → 3-tier scale detection → pixel-to-inch. Per-page dispatch in `pdf_takeoff.py`.
- Files: `backend/app/core/cv/{image_preprocessor,coordinate_converter,wall_line_extractor,scale_detector}.py`, `parsers/raster_parser.py`, `pdf_takeoff.py`

### 1.4 OCR Dimension Extraction — **DONE** (Sprints 4a, 4c)
Regex-based dimension parser (imperial ft-in / fractional / inches-only / word-form / metric mm/m) + Protocol-typed `OcrReader` DI. Lazy-init EasyOCR wrapper implements the Protocol.
- Files: `backend/app/core/cv/{dimension_parser,dimension_extractor,easyocr_reader}.py`

### 1.5 Scale Detection — **DONE** (Sprints 3b, 4f)
Two independent cascades:
- Raster (`ScaleDetector`): reference measurement > manual > ScaleWarning fallback.
- Vector PDF (`PDFParser._detect_scale`): manual > auto_text regex > 1:1 fallback with `scale_warning`.
Gemini Vision path (`floor_plan_service.py`) is scaffolded for a future auto-detect improvement.

### 1.6 Multi-Sheet Support — **PARTIAL** (Sprint 4e)
Multi-page PDF plans supported and page-tagged (`metadata["page"]`). Single-page scale detection only (page 0's scale is inherited by downstream pages). Multi-sheet DXF not yet built.

### 1.7 BIM/CAD Integration — **VISION**
Direct import from Revit (IFC/RVT), Navisworks, Bentley. Parse 3D BIM models for automated takeoff.

---

## 2. Computer Vision

### 2.1 Construction Object Detection (YOLOv8) — **PARTIAL**
Train YOLOv8 on construction drawings to detect studs, walls, doors, windows, and structural symbols. Detection service scaffolded but no trained model.
- Files: `backend/app/core/cv/detection_service.py`
- Data: `datascience/` contains initial training setup

### 2.2 Component Classification — **PLANNED**
Classify detected objects into construction categories (bearing wall vs partition, interior vs exterior door, window types).

### 2.3 Symbol Recognition — **PLANNED**
Recognize standard architectural symbols (electrical, plumbing, HVAC symbols) for future multi-trade expansion.

### 2.4 Progress Monitoring (Site Vision) — **VISION**
Camera/drone-based CV for construction progress tracking, as-built vs plan comparison. From broader proposal vision.

### 2.5 Safety/PPE Detection — **VISION**
Real-time PPE detection (hard hats, vests, glasses) and hazard identification on job sites. From proposal Safety AI module.

---

## 3. Material Takeoff & Calculation

### 3.1 Wall Framing (Studs & Plates) — **DONE**
Calculate stud quantities at 12"/16"/24" O.C. spacing, top plates (single/double), bottom plates. Configurable wall height. Sprint 5 enhancement: `LumberCalculator(kg_client=...)` populates `rule_citations` (IRC R602.3.x etc.) and `source_walls` (page-tagged wall IDs) on every `LumberMaterialItem`.
- Files: `backend/app/core/extraction/lumber_calculator.py`

### 3.2 Header Sizing — **PLANNED**
Calculate headers for door/window openings based on span and load. Beam solver exists but not connected to takeoff pipeline.
- Related: `backend/app/core/structural/beam_solver.py`

### 3.3 Complete Framing Package — **PLANNED**
Expand beyond wall studs/plates to include:
- Joists (floor/ceiling)
- Rafters and ridge boards
- Beams and posts
- Blocking and bridging
- Corner assemblies and T-intersections

### 3.4 Concrete & Foundation — **PLANNED**
Calculate concrete volume for footings, slabs, stem walls. Rebar quantities and spacing.

### 3.5 Drywall & Sheathing — **PLANNED**
Calculate sheet goods (drywall, OSB/plywood sheathing) with waste factor. Optimize sheet layout.

### 3.6 Fastener Calculation — **PLANNED**
Calculate nails, screws, bolts, tie-downs, and connectors per IRC/IBC nailing schedules.
- Depends on: 5.1 (Knowledge Graph for fastener rules)

### 3.7 Insulation & Vapor Barrier — **PLANNED**
Calculate insulation quantities by R-value and wall cavity dimensions.

### 3.8 Multi-Trade Expansion — **VISION**
Extend takeoff to electrical (wire, boxes, fixtures), plumbing (pipe, fittings), and HVAC (duct, diffusers). From proposal long-term vision.

---

## 4. Optimization

### 4.1 Cut List Optimization — **PLANNED**
Minimize waste via cutting stock algorithm (OR-Tools/PuLP). Map required pieces to standard lumber lengths (8', 10', 12', 16', 20'). Target: <5% waste.
- Directory exists: `backend/app/core/optimization/` (empty)

### 4.2 Material Substitution — **PLANNED**
Suggest equivalent alternatives when primary materials unavailable. Rank by cost, availability, structural equivalence.

### 4.3 Procurement Optimization — **VISION**
Optimize order quantities across suppliers, batch purchases, delivery scheduling. From proposal Procurement Agent concept.

---

## 5. Knowledge Graph

### 5.1 Neo4j Setup & Schema — **DONE** (Sprint 2)
Neo4j Community Edition self-hosted on GCE `e2-small` (10.150.0.2), reached from Cloud Run via Serverless VPC Access connector. Bolt driver + graceful degradation client. Live in prod.
- Files: `backend/app/core/kg/client.py`, `infra/main.tf`, `infra/README.md`

### 5.2 Seed Data: Lumber & Fasteners — **PARTIAL** (Sprint 2)
6 lumber specs seeded (`lumber_specs_loaded=6` in `/api/health/kg`). Fasteners and connectors not yet loaded.
- Files: `backend/app/core/kg/loader.py`

### 5.3 Seed Data: Building Codes (IRC) — **PARTIAL** (Sprint 2, 5)
Rule citations (IRC R602.3.x) wired through `cite_rule_for(item)` and stamped onto every `LumberMaterialItem`. Full IRC ruleset (span tables, nailing schedules, bearing, fire separation, egress) not yet loaded — needs 8.1.
- Files: `backend/app/core/kg/provenance.py`

### 5.4 Provenance Tracking — **PARTIAL** (Sprint 5)
Every BOM line traces to `source_walls` (page-tagged wall IDs) + `rule_citations`. Object catalog carries OCR validation labels (`confirmed` / `minor_discrepancy` / `mismatch`). Confidence scores per plan-fact not yet tracked.
- Files: `backend/app/core/kg/provenance.py`, `catalog/validation_summary.py`

### 5.6 KG Query Latency <100ms — **PLANNED** (Sprint 6)
Phase 1 §8 criterion 3. Needs benchmark harness against real query patterns (`cite_rule_for`, lumber-spec lookup). Requires Neo4j-in-CI (extend testcontainers or ephemeral GCE).

### 5.5 Historical Project Data — **VISION**
Store past project takeoffs for continuous learning. Use historical accuracy to calibrate future estimates.

---

## 6. Agent Framework

### 6.1 Base Agent Architecture — **PLANNED**
LangChain-based multi-agent system with shared KG access. Define agent interface, message passing, and orchestration.
- Directory exists: `backend/app/core/llm/` (empty)

### 6.2 Extraction QA Agent — **PLANNED**
Validates geometry/text extraction from plans. Flags low-confidence items, checks for missing walls, verifies scale consistency.

### 6.3 Component Inference Agent — **PLANNED**
Maps plan facts to structural assemblies using KG rules. Infers headers, cripple studs, king/trimmer studs from opening dimensions.

### 6.4 Code & Compliance Agent — **PLANNED**
Checks takeoff against IRC/IBC codes. Provides citations for every compliance decision. Flags violations.

### 6.5 Procurement & Cut Agent — **PLANNED**
Selects stock sizes, calls OR-Tools optimizer, generates BOM with supplier mappings.

### 6.6 Instruction Generation Agent — **PLANNED**
Generates step-by-step build instructions with code references. Includes framing sequence, fastener schedules, and inspection checkpoints.

### 6.7 Structural Hypothesis Agent — **PLANNED**
From VVUQ integration. Evaluates structural hypotheses using beam solver, Monte Carlo UQ, and Pareto ranking of alternatives.
- Reference: ADR-007 in `memory-bank/architecturalDecisions.md`

---

## 7. Structural Analysis (VVUQ)

### 7.1 Euler-Bernoulli Beam Solver — **DONE**
Finite-difference PDE solver for simply-supported beams. Computes deflection, moment, and shear fields.
- Files: `backend/app/core/structural/beam_solver.py`
- Benchmark: `benchmarks/structural/` (C++ port)

### 7.2 Monte Carlo Uncertainty Quantification — **PLANNED**
Propagate material property uncertainty (E, Fb, Fv) through beam solver. Generate confidence intervals on structural adequacy.

### 7.3 IRC Span Table Validation — **PLANNED**
Validate beam solver results against published IRC span tables. Part of V&V framework from proposal.

### 7.4 Multi-Hypothesis Structural Analysis — **PLANNED**
Generate and evaluate multiple structural configurations. Rank by Pareto criteria (cost, safety factor, deflection).

---

## 8. Code Compliance

### 8.1 IRC Residential Compliance Engine — **PLANNED**
Rule engine that checks framing against IRC requirements: stud spacing, bearing, header sizing, fire separation, egress.

### 8.2 Compliance Citations — **PLANNED**
Every compliance decision linked to specific IRC/IBC section number. Generates compliance report with pass/fail per code section.

### 8.3 Jurisdiction Overlays — **VISION**
Support local amendments to IRC (e.g., seismic zones, snow load regions, wind speed zones).

---

## 9. Output & Export

### 9.1 JSON Material List — **DONE**
JSON-formatted BOM with material items, quantities, specifications. Returned via API.

### 9.2 Labeled CAD Output — **PLANNED**
Generate DXF/DWG/SVG with labeled components (studs, plates, headers) overlaid on original plan.
- Directory exists: `backend/app/core/cad_generation/` (empty)

### 9.3 Cut List Report — **PLANNED**
Printable cut list showing each piece, its source stock, and cutting diagram. Depends on 4.1.

### 9.4 Build Instructions Document — **PLANNED**
Step-by-step framing instructions with code citations. Depends on 6.6.

### 9.5 Estimating Software Export — **VISION**
Export to common estimating platforms (STACK, PlanSwift format). From proposal integration vision.

### 9.6 Supplier Integration — **VISION**
Direct BOM submission to lumber suppliers for pricing and availability. From proposal Procurement Agent.

---

## 10. Web Application

### 10.1 File Upload & Processing — **DONE**
Upload DWG/DXF/PDF, configure parameters, trigger processing. React frontend with FastAPI backend.

### 10.2 Results Display — **DONE**
Show material takeoff results with quantities, specifications, and linear footage.

### 10.3 3D Visualization — **PLANNED**
Three.js-based 3D view of framed structure. React Three Fiber already in dependencies but not implemented.

### 10.4 Interactive Plan Markup — **PLANNED**
Click on plan elements to see component details, modify parameters, annotate issues.

### 10.5 User Authentication — **PLANNED**
Login, user accounts, role-based access. No auth currently implemented.

### 10.6 Project Management — **PLANNED**
Save, name, and organize multiple takeoff projects. Compare revisions.

### 10.7 Team Collaboration — **VISION**
Share projects, assign reviews, comment on takeoffs. From proposal Phase 8.

### 10.8 Mobile Field App — **VISION**
Mobile-optimized interface for on-site reference. From proposal presentation layer vision.

---

## 11. Infrastructure

### 11.1 Docker Compose Stack — **DONE**
PostgreSQL + FastAPI + React via docker-compose.yml.

### 11.2 Async Task Processing — **PLANNED**
Celery + Redis for background processing of large plans. Commented out in docker-compose.yml, ready to enable.

### 11.3 CI/CD Pipeline — **DONE** (Sprint 2b, 2c)
GitHub Actions:
- CI (`.github/workflows/ci.yml`) — pytest + coverage on every PR/push to master.
- CD (`.github/workflows/cd.yml`) — WIF auth → build → push to Artifact Registry → `gcloud run deploy` → smoke-test live URL. Fails CD if new revision isn't `ready`.

### 11.4 Cloud Deployment — **DONE** (Sprint 2c)
Cloud Run v2 backend (4 GiB / 2 CPU / scale-to-zero) + self-hosted Neo4j Community Edition on GCE + Artifact Registry + Secret Manager + Serverless VPC Access, all Terraform-managed in `vt-gcp-00042`. Backend live at <https://construction-ai-backend-542888988741.us-east4.run.app>. ≈$28/mo.

### 11.5 Edge Computing — **VISION**
On-site processing for low-latency and offline capability. From proposal infrastructure vision.

---

## Priority Guidance

**Immediate Phase 1 closeout** (in order):
1. Verify Sprint 4f (`/constellize:feature:verify sprint-4f-pdf-vector-parser-unit-fix`) — 4 quality gates against the 2026-07-02 implementation.
2. **5.6** KG Query Latency <100ms benchmark (Sprint 6) — closes Phase 1 §8 criterion 3.
3. User hand-counted plans → gated fixtures in `references.json` → Sprint 5's ≤10% wall-LF gate lights up.

**Next sprint candidates** (highest value, most dependencies unblocked):
1. **3.2** Header Sizing — beam solver exists and is verified; just needs pipeline integration in `lumber_calculator.py`. Fastest path to a new capability.
2. **4.1** Cut List Optimization — high user value, OR-Tools is a declared dependency, directory scaffolded.
3. **8.1** IRC Compliance Engine — core differentiator from competitors; consumes 5.2 + 5.3.
4. **6.1** Base Agent Architecture — proposal's 6-agent framework. `core/llm/` is empty.
5. **2.1** YOLOv8 retraining on construction-specific data — improve raster-drawing robustness.

**Quick wins** (small effort, existing infrastructure):
- **3.2** Header Sizing — connect existing `beam_solver.py` to takeoff pipeline.
- **5.2** Fastener spec seeding — extend `kg/loader.py`.
- **10.3** 3D Visualization — Three.js + R3F already in frontend deps.

**Recent completions (Sprints 3-5, 4f):**
- Raster/scanned drawing support (1.3), OCR dimension extraction (1.4), scale detection (1.5).
- Object catalog graph (was implicit in 5.4; now `catalog/`).
- Neo4j setup + provenance + partial IRC seed (5.1, 5.3, 5.4).
- CI/CD pipeline + Cloud deployment (11.3, 11.4).
