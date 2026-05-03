# Project Brief: Construction.AI

## One-Line Description

AI-powered web application that automates material takeoff from architectural drawings, calculating lumber quantities for wood-framed residential construction.

## Purpose

Reduce manual effort and errors in construction material estimation by automatically parsing floor plans (DWG/DXF/PDF/raster images), extracting wall geometry, and generating accurate lumber bills of materials including studs, plates, and headers.

## Target Users

- Residential construction contractors and estimators
- Habitat for Humanity build coordinators
- Framing subcontractors needing quick material lists from blueprints

## Problem Being Solved

Manual material takeoff from architectural drawings is time-consuming, error-prone, and requires specialized knowledge. This system automates the extraction of wall geometry from CAD/PDF floor plans and calculates framing lumber quantities following standard construction practices (stud spacing, plate runs, headers).

## Scope Boundaries

### In Scope

- Residential wood framing (new construction)
- 2D floor plan processing (DWG, DXF, PDF vector-based)
- Raster/scanned drawing support (JPG, PNG — specified, not yet implemented)
- Wall stud calculation (12", 16", 24" O.C. spacing)
- Top/bottom plate calculation (single and double top plate)
- Header sizing for openings
- JSON-formatted material lists
- Object detection via YOLOv8 (3 trained models in GCS)
- Scale detection via Google Gemini Vision
- OCR dimension extraction and validation (specified, not yet implemented)
- Model versioning and hot-swap via registry

### Out of Scope (Current Phase)

- Multi-trade expansion (electrical, plumbing, HVAC)
- Renovation/remodel scenarios
- Lateral/seismic structural analysis
- 3D BIM integration
- Cost estimation and pricing
- Multi-story buildings (planned for future)
- Cut list optimization (planned, OR-Tools integration not yet built)

## Key Constraints

- **Accuracy target**: 95%+ component detection from floor plans
- **Performance**: <2 min processing per project
- **Input formats**: DWG (auto-converted), DXF, PDF (vector), JPG/PNG (raster — planned)
- **Skew policy**: Skewed drawings are rejected, not corrected
- **Code compliance**: IRC residential building code (planned, not yet implemented)
- **Architecture**: Follows KG-centered design from companion proposal repo, but Neo4j not yet integrated
- **Model storage**: GCS with generation pinning for reproducibility

## Related Repository

- **Proposal repo**: `../construction-ai-proposal/` — IEEE conference paper, Beamer presentation, VVUQ analysis
- **Published**: https://djjay0131.github.io/construction-ai-proposal/
- The proposal describes a more ambitious multi-agent, KG-centered architecture; this repo implements the MVP subset
