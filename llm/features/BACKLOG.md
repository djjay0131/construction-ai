# Feature Backlog

All planned capabilities for Construction.AI, consolidated from the proposal repo, memory-bank vision docs, and README roadmap. Each item is a candidate for detailed specification via `constellize:feature:specify`.

Status key: **DONE** | **PARTIAL** | **PLANNED** | **VISION**

---

## 1. Plan Parsing & Extraction

### 1.1 DXF/DWG Parsing — **DONE**
Parse DXF files via ezdxf, auto-convert DWG via LibreDWG. Extract wall geometry as LINE/LWPOLYLINE entities with start/end coordinates and length.
- Files: `backend/app/core/parsers/dxf_parser.py`, `dwg_converter.py`

### 1.2 PDF Vector Extraction — **DONE**
Extract wall geometry from vector-based PDF floor plans using PyMuPDF path extraction.
- Files: `backend/app/core/parsers/pdf_parser.py`

### 1.3 Raster/Scanned Drawing Support — **PLANNED**
Support scanned drawings (JPG, PNG) via CV pipeline. Requires trained object detection model to identify walls, doors, windows from pixel data.
- Depends on: 2.1 (YOLOv8 training)

### 1.4 OCR Dimension Extraction — **PARTIAL**
Extract numeric dimensions and annotations from drawings using EasyOCR. Scaffolded but not integrated into main pipeline.
- Depends on: easyocr integration in parsing pipeline

### 1.5 Scale Detection — **PARTIAL**
Use Google Gemini Vision API to detect drawing scale from title blocks and scale bars. Service exists but integration with takeoff pipeline is incomplete.
- Files: `backend/app/core/cv/floor_plan_service.py`

### 1.6 Multi-Sheet Support — **PLANNED**
Handle multi-page PDF plans and multi-sheet DXF files, mapping sheets to floors/sections.

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
Calculate stud quantities at 12"/16"/24" O.C. spacing, top plates (single/double), bottom plates. Configurable wall height.
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

### 5.1 Neo4j Setup & Schema — **PLANNED**
Deploy Neo4j and implement the KG schema from the proposal:
```
Project → PlanSheet → PlanFact → AssemblyIntent → Component → StockItem → CutPiece
Component → FastenerRule, CodeRule
Project → SupplierCatalogItem
```
- Reference: `memory-bank/techContext.md` (schema diagram)

### 5.2 Seed Data: Lumber & Fasteners — **PLANNED**
Populate KG with standard lumber dimensions, grades, fastener types, and connector specifications.

### 5.3 Seed Data: Building Codes (IRC) — **PLANNED**
Populate KG with IRC residential code rules (span tables, nailing schedules, bearing requirements, fire separation).

### 5.4 Provenance Tracking — **PLANNED**
Track the origin and confidence of every fact in the KG. Link decisions to source documents, code sections, and agent reasoning.

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

### 11.3 CI/CD Pipeline — **PLANNED**
GitHub Actions for test, build, deploy. Exists for proposal repo but not for implementation repo.

### 11.4 Cloud Deployment — **VISION**
Production deployment on AWS/GCP. From proposal infrastructure section.

### 11.5 Edge Computing — **VISION**
On-site processing for low-latency and offline capability. From proposal infrastructure vision.

---

## Priority Guidance

**Next sprint candidates** (highest value, most dependencies unblocked):
1. **5.1** Neo4j Setup — unlocks KG-dependent features (5.2, 5.3, 6.x)
2. **4.1** Cut List Optimization — high user value, OR-Tools is a declared dependency
3. **3.2** Header Sizing — beam solver exists, just needs pipeline integration
4. **2.1** YOLOv8 Training — unlocks CV-based extraction for raster inputs
5. **8.1** IRC Compliance Engine — core differentiator from competitors

**Quick wins** (small effort, existing infrastructure):
- **1.4** OCR Dimension Extraction — easyocr is installed, needs integration
- **3.2** Header Sizing — connect existing beam_solver.py to takeoff pipeline
- **10.3** 3D Visualization — Three.js already in frontend deps
