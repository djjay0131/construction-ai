# Sprint 01: Foundation Setup

**Status:** Not Started
**Target Start:** TBD
**Estimated Duration:** 1-2 weeks

## Goals

1. Review and document existing codebase
2. Set up development environment
3. Establish Neo4j Knowledge Graph foundation
4. Create basic API structure aligned with proposal architecture

## Prerequisites

- Docker and docker-compose installed
- Node.js for frontend development
- Python 3.11+ for backend
- Neo4j database (via Docker)

## Tasks

### 1. Codebase Review

- [ ] Document existing backend structure
- [ ] Document existing frontend structure
- [ ] Identify reusable components
- [ ] Map existing code to proposal architecture
- [ ] List gaps between current and target architecture

### 2. Development Environment

- [ ] Verify docker-compose configuration
- [ ] Test all services start correctly
- [ ] Set up Neo4j container with proper volumes
- [ ] Configure environment variables
- [ ] Create development setup documentation

### 3. Knowledge Graph Foundation

- [ ] Design Neo4j schema based on proposal Section 3
- [ ] Create entity types:
  - Component (Wall, Door, Window, Header, Stud, Plate)
  - Material (lumber grades, dimensions)
  - Fastener (nails, screws, hangers)
  - CodeRule (IRC references)
- [ ] Create relationship types:
  - CONTAINS, REQUIRES, COMPATIBLE_WITH
  - GOVERNED_BY, DERIVED_FROM
- [ ] Implement seed data loader
- [ ] Write basic Cypher queries for testing

### 4. API Structure

- [ ] Define API routes aligned with proposal phases:
  - `/api/extract` - Plan parsing
  - `/api/infer` - Component inference
  - `/api/optimize` - Cut optimization
  - `/api/export` - BOM generation
- [ ] Set up basic FastAPI structure
- [ ] Implement health check endpoints
- [ ] Add Neo4j connection handling

## Acceptance Criteria

- [ ] All Docker services start without errors
- [ ] Neo4j accessible with schema loaded
- [ ] API returns health check successfully
- [ ] Basic KG queries return expected data
- [ ] Documentation updated with findings

## Reference

- Proposal Architecture: `../construction-ai-proposal/proposal/sections/02-architecture.tex`
- KG Design: `../construction-ai-proposal/proposal/sections/03-knowledge-graph.tex`
- Published Proposal: https://djjay0131.github.io/construction-ai-proposal/

## Notes

- Focus on foundation; don't implement full features yet
- Document any deviations from proposal architecture
- Create issues for discovered technical debt
