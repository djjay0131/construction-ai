# Project Brief: Construction.AI Implementation

## Core Objectives

Build the **implementation** of Construction.AI - an AI-powered Material Takeoff and Construction Recommendations system. This repository contains the working prototype following the architecture defined in the [construction-ai-proposal](../construction-ai-proposal/).

## Primary Focus Areas

### 1. Material Takeoff Automation

- Automated quantity extraction from blueprints/drawings (PDF, DXF)
- AI-powered measurement and calculation
- Component inference from floor plans
- Accuracy validation and error detection

### 2. Knowledge Graph System

- Neo4j-based knowledge graph for construction data
- Material properties, fasteners, code requirements
- Provenance tracking for all decisions
- Historical project data for continuous learning

### 3. Agentic Workflow

- Multi-agent system (5 specialized agents)
- Extraction QA Agent
- Component Inference Agent
- Code & Compliance Agent
- Procurement Agent
- Instruction Generation Agent

### 4. Construction Recommendations

- AI-driven construction methodology suggestions
- Cut optimization (OR-Tools)
- Material substitution alternatives
- Code compliance guidance with citations

## Requirements

### Functional Requirements

- Parse PDF and DXF floor plans
- Extract components (walls, doors, windows)
- Infer structural elements (headers, studs, plates)
- Generate optimized cut lists
- Produce build instructions with code citations
- Export to JSON for supplier integration

### Technical Requirements

- Computer vision for drawing interpretation (YOLOv8)
- OCR for dimension extraction (EasyOCR)
- Knowledge graph for construction rules (Neo4j)
- Optimization engine (OR-Tools)
- LLM agents for reasoning (Claude/GPT-4)

## Success Criteria

- [ ] Plan parsing with 95%+ component detection
- [ ] KG queries under 100ms response time
- [ ] Cut optimization with <5% waste
- [ ] Code compliance for IRC residential
- [ ] Build instructions with provenance chains
- [ ] <2 min processing per project

## Project Constraints

### In Scope

- Residential wood framing (new construction)
- 2D floor plan processing
- Vertical load paths (gravity loads)
- IRC code compliance
- Single-trade focus (framing)

### Out of Scope (Initial Phase)

- Multi-trade expansion (electrical, plumbing)
- Renovation/remodel scenarios
- Lateral/seismic analysis
- 3D BIM integration
- Cost estimation/pricing

## Related Repository

**Proposal Repository:** [construction-ai-proposal](../construction-ai-proposal/)

- Research proposal and academic documentation
- Published at: https://djjay0131.github.io/construction-ai-proposal/
- Architecture diagrams and design rationale
- VVUQ integration (physics-based structural analysis)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI |
| Frontend | React, TypeScript |
| Knowledge Graph | Neo4j |
| ML/Vision | PyTorch, YOLOv8, EasyOCR |
| Optimization | OR-Tools |
| LLM Agents | Claude API, LangChain |
| Deployment | Docker, docker-compose |

## Contact & Resources

- Implementation Repository: construction-ai
- Proposal Repository: construction-ai-proposal
- Published Docs: https://djjay0131.github.io/construction-ai-proposal/

---

**Note:** This brief establishes the implementation foundation. Refer to the proposal repo for research and academic context.
