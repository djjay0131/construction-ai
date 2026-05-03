# Feature: OCR Dimension Extraction & Object Catalog

**Status:** SPECIFIED (reviewed)
**Date:** 2026-04-01
**Author:** Feature Architect (AI-assisted)

## Problem

The system captures raw OCR text from drawings but discards the structured data: EasyOCR bounding box positions are thrown away (only concatenated text is kept), Gemini Vision's `dimensions` array is ignored, and `PDFParser.extract_text()` is never called from the takeoff pipeline. Dimension annotations on floor plans — the architect's intended measurements — are completely unused during takeoff. Additionally, there is no structured representation of what's in a drawing: which walls exist, how they connect, what doors/windows they contain, and what their dimensions are.

This feature solves two linked problems:
1. **Dimension extraction** — Parse OCR text into structured numeric measurements and associate them with specific drawing elements
2. **Object catalog** — Build a persistent, graph-based catalog of all architectural elements, their dimensions, spatial relationships, and validation status

The object catalog is an **architectural-level** representation ("what's in the drawing") — distinct from the framing-level decomposition in backlog items 5.1/6.3 ("how to build it"), which breaks walls into studs, headers, king studs, etc.

## Goals

- Parse architectural dimension annotations into structured numeric values (e.g., `12'-6"` → 150 inches)
- Associate parsed dimensions with the correct drawing element via spatial proximity
- Build a persistent graph-based object catalog of all identified elements (walls, doors, windows, openings) with their dimensions, locations, and relationships
- Scale-based geometric measurement is the **primary measurement source** (drawings are assumed to-scale)
- OCR dimensions serve as **validation** — confirm or flag discrepancies against geometric measurements
- Skewed drawings are rejected with a clear error message (no deskew correction for now)
- Persist the catalog as a permanent artifact alongside the drawing (format TBD — see Technical Notes on storage format experiment)
- Design the catalog interface so storage format (flat JSON vs NetworkX graph vs Neo4j) can be swapped without changing consumers

## Non-Goals

- Framing-level decomposition (studs, plates, headers, jack studs, king studs, sill plates) — that's backlog 5.1 / 6.3
- Neo4j integration — use NetworkX + JSON for now, migrate later
- Handwritten dimension recognition — typed/printed annotations only
- Dimension line/leader/arrow detection — associate by text proximity, not by tracing graphical leaders
- Multi-sheet cross-referencing (e.g., "See Detail A on Sheet 3")

## User Stories

- As a contractor, I want dimension annotations on the drawing to be automatically read and compared against the geometric measurements, so that I'm alerted if the takeoff dimensions don't match what the architect annotated.
- As a project manager, I want to see a structured catalog of every wall, door, and window in the drawing with their relationships, so that I can verify the extraction is complete before running a takeoff.
- As an estimator, I want to be alerted when a geometrically-measured wall length differs significantly from its annotated dimension, so that I can investigate before the error propagates into material quantities.

## Design Approach

### Architecture

The feature adds two new components that sit between the existing parsers/CV and the takeoff pipeline:

```
Drawing Input (any format)
       │
       ▼
Existing Parsers / CV Detection
  (walls, doors, windows as bboxes/lines)
       │
       ├──────────────────────────────┐
       ▼                              ▼
DimensionExtractor              ObjectCatalogBuilder
  ├── EasyOCR (keep bboxes!)      ├── Create nodes from detections
  ├── Gemini Vision dimensions    ├── Build edges (connections, containment)
  ├── Regex parsing → inches      ├── Attach OCR dimensions to nodes
  └── Spatial association         ├── Validate OCR vs geometry
       │                          ├── Flag discrepancies
       └──────────┬───────────────┘
                  ▼
         NetworkX Graph
         (persisted as JSON/GraphML)
                  │
                  ▼
         LumberCalculator
         (reads wall lengths from catalog,
          prefers OCR source over geometric)
```

### Graph Schema

**Nodes:**

| Node Type | Properties |
|-----------|-----------|
| `Wall` | `id`, `start_point` (px), `end_point` (px), `length_in`, `length_in_geometric`, `length_source` ("geometric"\|"ocr_fallback"), `ocr_dimension_in`, `ocr_validation` ("confirmed"\|"minor_discrepancy"\|"mismatch"\|null), `bbox_px`, `orientation` ("horizontal"\|"vertical"\|"diagonal"), `confidence`, `validation_flags[]`, `ocr_labels[]` |
| `Door` | `id`, `width_in`, `height_in`, `door_type` ("standard"\|"sliding"\|"double"), `bbox_px`, `confidence`, `ocr_labels[]` |
| `Window` | `id`, `width_in`, `height_in`, `bbox_px`, `confidence`, `ocr_labels[]` |
| `Opening` | `id`, `width_in`, `bbox_px`, `confidence` |
| `Room` | `id`, `label` (from OCR room name), `area_sqft`, `bbox_px` |

**Edges:**

| Edge Type | From → To | Properties |
|-----------|-----------|-----------|
| `CONNECTS_TO` | Wall → Wall | `junction_type` ("corner"\|"tee"\|"cross"), `junction_point_px` |
| `CONTAINS` | Wall → Door/Window/Opening | `position_along_wall` (0.0-1.0), `offset_from_start_in` |
| `BOUNDS` | Wall → Room | `side` ("north"\|"south"\|"east"\|"west") |

### Key Components

1. **`DimensionExtractor`** (`backend/app/core/cv/dimension_extractor.py`) — Runs EasyOCR preserving bounding boxes, parses architectural notation via regex patterns (imperial ft-in, inches-only, metric), returns structured dimension objects with position and parsed value.

2. **`ObjectCatalogBuilder`** (`backend/app/core/catalog/catalog_builder.py`) — Takes YOLO detections + wall geometry + parsed dimensions, builds a NetworkX graph with nodes for each element, edges for spatial relationships (connections, containment), and attaches OCR dimensions with validation against geometric measurements.

3. **`CatalogStore`** (`backend/app/core/catalog/catalog_store.py`) — Serializes/deserializes the NetworkX graph to JSON (node-link format) or GraphML. Stores as a file artifact in the project's analysis directory. Provides query methods (get all walls, get wall connections, get elements with validation flags).

4. **`DimensionParser`** (`backend/app/core/cv/dimension_parser.py`) — Pure function: regex-based parsing of architectural dimension strings into inches. Handles imperial (`12'-6"`, `12'`, `36"`), metric (`3600mm`, `3.6m`), and fractional (`12'-6 1/2"`) formats. No I/O, easily testable.

5. **Takeoff pipeline update** — `takeoff.py` reads wall lengths from the catalog (preferring OCR-sourced dimensions), passes to `LumberCalculator`. Includes validation flags in takeoff notes.

### Measurement Trust Hierarchy

1. **Scale-based geometric measurement** (highest trust) — drawing is assumed to-scale, wall length calculated from geometry + detected scale ratio
2. **OCR dimension annotations** (validation) — parsed dimensions compared against geometric measurement. If they agree (within 10%), confidence increases. If they disagree (>15%), flag for user review.
3. **No scale available** → fall back to OCR dimensions as primary source, or reject if neither exists

### Skew Policy

Skewed drawings (detected via dominant line angle analysis) are **rejected** with a clear error message rather than silently corrected. Rationale: if the drawing is skewed, geometric measurements from scale will be wrong, and the system should not produce silently inaccurate takeoffs.

### Spatial Association Algorithm

**V1: Proximity-based (initial implementation)**

For each parsed OCR dimension:
1. Compute centroid of OCR text bounding box
2. For each candidate element, compute minimum distance from text centroid to element bbox edge
3. Filter candidates to elements within a distance threshold (scaled by drawing DPI)
4. Among candidates, prefer walls oriented parallel to the dimension text baseline
5. If ambiguous (multiple elements equidistant), flag as `validation_flag: "ambiguous_dimension_association"` and assign to the longest candidate

Note: Since OCR dimensions are used for **validation only** (not as the primary measurement), misassociation is less critical — a wrong association produces a false mismatch flag, which the user reviews. It does not corrupt the takeoff.

**V2: Leader line detection (planned enhancement)**

Dimension annotations on architectural drawings include leader lines (thin lines with arrowheads/ticks) connecting the text to the measured element's start and end points. Detecting these leader lines would provide definitive association:
1. Detect thin line segments near OCR text bboxes (Hough lines with lower thickness threshold)
2. Identify arrowhead/tick endpoints
3. Match leader line endpoints to element edges
4. Associate dimension text with the element whose edges match the leader line endpoints

This is the architecturally correct approach and should replace proximity-based association when the CV pipeline is mature enough to reliably detect thin leader lines.

## Sample Implementation

```python
# dimension_extractor.py — Core OCR dimension extraction

import re
import numpy as np
from dataclasses import dataclass, field

@dataclass
class ParsedDimension:
    raw_text: str
    value_inches: float
    bbox: list  # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] from EasyOCR
    center: tuple[float, float]
    confidence: float
    format: str  # "ft_in", "ft_only", "in_only", "mm", "m"

class DimensionParser:
    """Parse architectural dimension strings into inches."""

    PATTERNS = [
        # 12'-6 1/2" (feet, inches, fraction)
        (r"(\d+)\s*['']\s*-?\s*(\d+)\s+(\d+)/(\d+)\s*[\"""]", "ft_in_frac"),
        # 12'-6", 12' - 6", 12'6"
        (r"(\d+)\s*['']\s*-?\s*(\d+(?:\.\d+)?)\s*[\"""]", "ft_in"),
        # 12'-0", 12'
        (r"(\d+)\s*['']\s*-?\s*0?\s*[\"""]?$", "ft_only"),
        # 6", 36", 150.5"
        (r"^(\d+(?:\.\d+)?)\s*[\"""]$", "in_only"),
        # 3600mm
        (r"(\d+(?:\.\d+)?)\s*mm", "mm"),
        # 3.6m
        (r"(\d+(?:\.\d+)?)\s*m\b", "m"),
    ]

    def parse(self, text: str) -> float | None:
        text = text.strip()
        for pattern, fmt in self.PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            if fmt == "ft_in_frac":
                ft, inch, num, den = match.groups()
                return float(ft) * 12 + float(inch) + float(num)/float(den)
            elif fmt == "ft_in":
                return float(match.group(1)) * 12 + float(match.group(2))
            elif fmt == "ft_only":
                return float(match.group(1)) * 12
            elif fmt == "in_only":
                return float(match.group(1))
            elif fmt == "mm":
                return float(match.group(1)) / 25.4
            elif fmt == "m":
                return float(match.group(1)) * 39.3701
        return None


class DimensionExtractor:
    """Extract and parse dimensions from drawing images via OCR."""

    def __init__(self):
        self.ocr_reader = easyocr.Reader(['en'], gpu=True)
        self.parser = DimensionParser()

    def extract(self, image: np.ndarray) -> list[ParsedDimension]:
        # EasyOCR returns (bbox, text, confidence) — KEEP bboxes
        ocr_results = self.ocr_reader.readtext(image)
        dimensions = []

        for bbox, text, conf in ocr_results:
            value = self.parser.parse(text)
            if value is not None:
                center = np.mean(bbox, axis=0)
                dimensions.append(ParsedDimension(
                    raw_text=text, value_inches=value,
                    bbox=bbox, center=tuple(center),
                    confidence=conf, format="parsed",
                ))
        return dimensions


# catalog_builder.py — Build object catalog as NetworkX graph

import networkx as nx

class ObjectCatalogBuilder:
    """Build a persistent graph catalog of drawing elements."""

    DISCREPANCY_THRESHOLD = 0.15  # 15%

    def build(self, detections, wall_lines, dimensions, scale) -> nx.Graph:
        G = nx.Graph()

        # 1. Create nodes from YOLO detections + wall geometry
        for det in detections:
            node_id = f"{det.class_name.lower()}-{det.id}"
            G.add_node(node_id, element_type=det.class_name.lower(),
                       bbox_px=(det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2),
                       confidence=det.confidence, validation_flags=[],
                       ocr_labels=[], length_source="geometric")

            # Attach geometric length for walls
            if det.class_name == "Wall":
                geom_length = self._geometric_wall_length(det, wall_lines, scale)
                G.nodes[node_id]["length_in_geometric"] = geom_length
                G.nodes[node_id]["length_in"] = geom_length  # default

        # 2. Associate OCR dimensions with nearest elements
        for dim in dimensions:
            node_id = self._find_nearest_element(dim, G)
            if not node_id:
                continue

            node = G.nodes[node_id]
            node["ocr_labels"].append(dim.raw_text)

            if node["element_type"] == "wall":
                # Geometry is primary; OCR validates
                geom = node.get("length_in")  # already set from scale-based geometry
                node["ocr_dimension_in"] = dim.value_inches

                if geom:
                    diff = abs(dim.value_inches - geom) / geom
                    if diff <= 0.10:
                        node["ocr_validation"] = "confirmed"
                    elif diff <= self.DISCREPANCY_THRESHOLD:
                        node["ocr_validation"] = "minor_discrepancy"
                    else:
                        node["ocr_validation"] = "mismatch"
                        node["validation_flags"].append(
                            f"ocr_geometry_mismatch: geom={geom:.1f}in, "
                            f"OCR={dim.value_inches:.1f}in ({diff:.0%} diff)"
                        )
                else:
                    # No geometric measurement — fall back to OCR
                    node["length_in"] = dim.value_inches
                    node["length_source"] = "ocr_fallback"

        # 3. Build spatial relationships using LINE ENDPOINTS (not YOLO bboxes)
        #    YOLO bboxes are too imprecise for connection detection.
        #    Wall connections require endpoint-level accuracy from Hough lines
        #    or vector geometry (DXF/PDF paths).
        wall_nodes = [n for n, d in G.nodes(data=True) if d["element_type"] == "wall"]
        other_nodes = [n for n, d in G.nodes(data=True) if d["element_type"] != "wall"]

        ENDPOINT_TOLERANCE_PX = 10  # pixels — walls within this distance are "connected"

        for i, w1 in enumerate(wall_nodes):
            w1_data = G.nodes[w1]
            for w2 in wall_nodes[i+1:]:
                w2_data = G.nodes[w2]
                # Use line start/end points, NOT bounding boxes
                jtype = self._detect_junction_from_endpoints(
                    w1_data["start_point"], w1_data["end_point"],
                    w2_data["start_point"], w2_data["end_point"],
                    tolerance=ENDPOINT_TOLERANCE_PX
                )
                if jtype:
                    G.add_edge(w1, w2, relationship="CONNECTS_TO", junction_type=jtype)

            for other in other_nodes:
                if self._bbox_contains(w1_data["bbox_px"], G.nodes[other]["bbox_px"]):
                    G.add_edge(w1, other, relationship="CONTAINS")

        return G
```

## Edge Cases & Error Handling

### OCR Misread Characters
- **Scenario**: EasyOCR reads `12'-6"` as `l2'-6"` or `12'-6''` (curly quotes)
- **Behavior**: `DimensionParser` regex patterns accept common OCR substitutions: `l`/`1`, `O`/`0`, various quote styles (`"`, `"`, `''`, `″`). Text that matches no pattern is silently skipped (not an error).
- **Test**: Feed known-misread strings through `DimensionParser.parse()`. Verify `l2'-6"` → 150.0, `12\u201d` → None or handled.

### Ambiguous Dimension Association
- **Scenario**: A dimension annotation `10'-0"` sits equidistant between two parallel walls
- **Behavior**: Flag as `validation_flag: "ambiguous_dimension_association"`, assign to the longest candidate wall (more likely to be the one dimensioned). Include both candidate IDs in the flag.
- **Test**: Create synthetic image with two parallel walls and a centered dimension. Verify the flag is set and the longer wall gets the dimension.

### No Dimension Annotations Found
- **Scenario**: Drawing has no readable dimension text (clean floor plan without annotations)
- **Behavior**: Catalog is still built with geometric measurements only. All wall nodes have `length_source: "geometric"`. A warning note is added: "No OCR dimensions found — all measurements are geometric estimates."
- **Test**: Upload an unannotated floor plan. Verify catalog builds successfully with geometric-only lengths.

### Duplicate Dimensions for Same Element
- **Scenario**: Two OCR texts near the same wall both parse as valid dimensions (e.g., overall dimension and segment dimension)
- **Behavior**: Keep the dimension whose text centroid is closest to the wall midpoint. Store the other in `ocr_labels` for reference but don't use it as the primary length.
- **Test**: Create image with a wall that has both `24'-0"` (overall) and `12'-0"` (segment) annotations. Verify the closer one is used.

### Metric vs Imperial Mix
- **Scenario**: Drawing contains both metric and imperial dimensions
- **Behavior**: Parse all dimensions to inches regardless of source format. Store original format in `ParsedDimension.format`. If a mix of metric and imperial is detected on the same drawing, add a catalog-level warning.
- **Test**: Feed a drawing with `3600mm` and `12'-0"` annotations. Verify both parse correctly and the mixed-format warning is raised.

### Graph Persistence Failure
- **Scenario**: Disk full or permissions error when saving the catalog JSON
- **Behavior**: Log error, return catalog in-memory but warn user that persistence failed. Takeoff still proceeds with the in-memory catalog.
- **Test**: Mock filesystem write failure. Verify takeoff completes and warning is returned.

### Server Restart / Cache Loss
- **Scenario**: Server restarts and the `FloorPlanAnalysisService` in-memory cache is lost. User wants to access a previously generated catalog.
- **Behavior**: The catalog JSON is a permanent file artifact stored at `{UPLOAD_DIR}/analysis/{analysis_id}/catalog.json`. It is also linked to the `Drawing` record in the database via `MaterialTakeoffRecord.processing_metadata["catalog_path"]`. On restart, catalogs are loaded from disk on demand, not from the in-memory cache.
- **Test**: Save a catalog, restart the service, request the catalog by analysis_id. Verify it loads from disk.

### Very Large Drawings (>100 Elements)
- **Scenario**: Complex commercial floor plan with hundreds of walls, doors, windows
- **Behavior**: Spatial association uses a KD-tree (from scipy) for nearest-neighbor lookup instead of brute-force, keeping association O(n log n). Graph serialization to JSON handles large graphs natively.
- **Test**: Generate synthetic catalog with 500 elements. Verify association completes in <5 seconds and JSON serialization succeeds.

## Acceptance Criteria

### AC-1: Dimension Parsing
- **Given** a drawing image containing architectural dimension annotations (e.g., `12'-6"`, `24'`, `36"`)
- **When** OCR dimension extraction runs
- **Then** each dimension is parsed into a numeric value in inches with >95% parse accuracy on cleanly printed text

### AC-2: Spatial Association
- **Given** parsed OCR dimensions and detected drawing elements
- **When** spatial association runs
- **Then** each dimension is associated with the correct nearest element, verifiable by visual inspection on annotated output

### AC-3: Object Catalog Construction
- **Given** a processed floor plan with detected walls, doors, and windows
- **When** the catalog builder runs
- **Then** a NetworkX graph is produced with nodes for each element, `CONNECTS_TO` edges between walls sharing endpoints, and `CONTAINS` edges for doors/windows within walls

### AC-4: Graph Persistence
- **Given** a completed object catalog
- **When** the catalog is saved
- **Then** a JSON file is written to the analysis directory that can be loaded back into an identical NetworkX graph

### AC-5: OCR Validates Geometry
- **Given** a wall with a scale-based geometric measurement (`150.3 inches`) and an OCR dimension (`12'-6"` = 150 inches)
- **When** the catalog is built
- **Then** the wall's `length_in` is `150.3` (from geometry, the primary source), `length_source` is `"geometric"`, `ocr_validation` is `"confirmed"`, and both values are stored

### AC-6: Discrepancy Flagging
- **Given** a wall where OCR dimension and geometric measurement differ by >15%
- **When** the catalog is built
- **Then** the wall node has a `validation_flag` containing `"ocr_geometry_mismatch"` with both values

### AC-7: Takeoff Integration
- **Given** a catalog with scale-based geometric wall lengths and OCR validation results
- **When** the takeoff pipeline runs
- **Then** `LumberCalculator` uses geometric lengths (primary source), and the takeoff notes include OCR validation status (confirmed/mismatch count) and list any walls with validation flags

### AC-10: Skewed Drawing Rejection
- **Given** an uploaded drawing image with >5 degrees of skew detected
- **When** processing is attempted
- **Then** the system rejects the drawing with a clear error message explaining that skewed drawings are not supported and suggesting the user provide a properly scanned image

### AC-8: Catalog Query API
- **Given** a persisted object catalog
- **When** a user requests the catalog via API
- **Then** the response includes all elements, their dimensions, connections, containment relationships, and any validation flags

### AC-9: Graceful Degradation
- **Given** a drawing with no readable dimension annotations
- **When** OCR extraction finds nothing parseable
- **Then** the catalog is still built with geometric measurements only, and the takeoff proceeds with a warning

## Technical Notes

- **Affected components:**
  - `backend/app/core/cv/floor_plan_service.py` — modify `readtext()` call to preserve bboxes, use Gemini `dimensions` response
  - `backend/app/core/cv/dimension_extractor.py` — new: OCR extraction with bbox preservation
  - `backend/app/core/cv/dimension_parser.py` — new: pure regex parsing, no I/O
  - `backend/app/core/catalog/catalog_builder.py` — new: NetworkX graph construction
  - `backend/app/core/catalog/catalog_store.py` — new: JSON/GraphML serialization
  - `backend/app/api/takeoff.py` — read wall lengths from catalog instead of raw parser output
  - `backend/app/api/catalog.py` — new: API endpoints for catalog retrieval and query

- **Patterns to follow:**
  - Singleton service pattern (matches `get_detection_service()`)
  - Pydantic schemas for API responses
  - Parser interface: `load()`, `extract_walls()`, `get_drawing_info()`
  - Catalog stored alongside analysis artifacts in `{UPLOAD_DIR}/analysis/{analysis_id}/`

- **Data model changes:**
  - New file artifact: `catalog_{analysis_id}.json` — NetworkX node-link JSON
  - `MaterialTakeoffRecord.processing_metadata` — add `catalog_path`, `dimension_sources` summary
  - `MaterialTakeoff.notes` — include OCR/geometric source info and validation flags

- **Dependencies (already installed):**
  - `easyocr` — OCR with bounding boxes
  - `networkx` — graph construction and serialization (needs to be added to requirements)
  - `numpy` — spatial math
  - `scipy` (optional) — KD-tree for large-drawing spatial association

- **New dependency (conditional):**
  - `networkx` — only needed if `GraphCatalogStore` experiment proves valuable. Not required for `JsonCatalogStore` default.

## Dependencies

- **Existing `FloorPlanAnalysisService`** — EasyOCR reader and Gemini Vision integration reused. Must modify to preserve OCR bboxes.
- **Existing `DetectionService`** — YOLO detections provide the element bounding boxes that dimensions are associated with.
- **Raster Drawing Support (feature spec)** — The raster pipeline produces YOLO detections and Hough wall lines that feed into the catalog builder. OCR dimensions serve as the reference measurement for scale plausibility checks defined in that spec.
- **NetworkX** — new dependency, must be added to `requirements.txt`.
- **YOLO model storage** — The 2 trained models (~50MB+ each) currently live in local paths (`datascience/runs/`, `backend/app/core/cv/best.pt`). Needs a proper large file storage solution (GCP Cloud Storage, Artifact Registry, etc.) — to be specified separately.

## Storage Format Experiment

The catalog needs to be persisted, but the optimal format is unclear. The immediate consumer (`LumberCalculator`) needs a flat list of wall lengths. The future consumers (LLM agents in backlog 6.x) may benefit from graph structure for reasoning about spatial relationships.

**Experiment:** Implement the catalog behind an abstract `CatalogStore` interface with two concrete implementations:
1. **`JsonCatalogStore`** — flat JSON with elements list + relationships list. Simple, no new dependencies.
2. **`GraphCatalogStore`** — NetworkX graph serialized to node-link JSON. Richer querying, new dependency.

Test both formats with the agents (once backlog 6.x begins) to determine whether graph structure improves agent reasoning quality. Until then, default to `JsonCatalogStore`.

**Migration to Neo4j:** Both formats map cleanly to Neo4j nodes/relationships when backlog 5.1 lands. The abstract interface means swapping in `Neo4jCatalogStore` requires no consumer changes.

## Open Questions

- **EasyOCR vs Gemini for dimension extraction:** EasyOCR gives precise bboxes but may misread characters. Gemini gives structured dimension lists but without pixel positions. Should we run both and cross-validate, or prefer one?
- **Room label association:** OCR can detect room names ("MASTER BEDROOM", "KITCHEN"). Should the catalog include Room nodes bounded by walls? This adds value but increases complexity of the spatial association.
- **Dimension line detection:** Currently we associate by text proximity. Detecting the actual dimension lines (the graphical lines with arrows/ticks connecting the text to the measured element) would improve accuracy but requires additional CV work. Defer or include?
- **Catalog versioning:** Should catalogs be versioned (e.g., user corrects a dimension, new version is saved)? Or is overwrite-on-reprocess sufficient for v1?
- **Wall endpoint precision:** Connection detection requires accurate wall start/end points. For vector formats (DXF/PDF), this is exact. For raster, Hough line endpoints may need refinement (e.g., snap-to-grid, corner detection). What tolerance is acceptable for "perfect" connections? The current spec uses 10px but this may need tuning.
- **YOLO enhancement for endpoints:** If YOLO needs to provide endpoint-level accuracy (not just bounding boxes), this may require a custom model that predicts keypoints rather than boxes — a significant scope increase beyond backlog 2.1. Evaluate whether Hough endpoints are sufficient or if keypoint detection is needed.
