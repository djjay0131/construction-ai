# JSON Export Feature Documentation

## Overview
The floor plan analysis system now supports exporting complete analysis results as downloadable JSON files. This allows users to save detailed measurements, object detections, and metadata for external processing, reporting, or archival.

## Features

### 1. Export Floor Plan Analysis with Detections
**Endpoint**: `GET /api/floor-plan/export/{analysis_id}/floor-plan/{floor_plan_id}`

Exports comprehensive JSON report including:
- Document metadata (filename, paper size, resolution, DPI)
- Scale information (notation, ratio, conversion factors)
- Floor plan dimensions (pixels, paper inches, real-world measurements)
- Detected objects grouped by class (wall, door, window, etc.)
- Object-specific measurements:
  - Doors: Width and height in inches and feet
  - Walls: Length in feet and thickness in inches
  - Windows: Width and height dimensions
- Bounding box coordinates for each object
- Summary statistics (counts, averages, ranges, totals)

### 2. Export Initial Analysis
**Endpoint**: `GET /api/floor-plan/export/{analysis_id}`

Exports basic analysis including:
- Document information
- Paper size details
- All detected floor plans with their dimensions
- Scale information

## JSON Structure

### Complete Floor Plan Analysis JSON

```json
{
  "analysis_id": "uuid-string",
  "floor_plan_id": 1,
  "generated_at": "2026-01-06 10:30:45",
  "document_info": {
    "filename": "example.pdf",
    "paper_size": "ANSI B (Tabloid)",
    "paper_dimensions_inches": {
      "width": 17.0,
      "height": 11.0
    },
    "page_resolution_pixels": {
      "width": 5100,
      "height": 3300
    },
    "dpi": 300,
    "pixels_per_inch": {
      "width": 300.0,
      "height": 300.0
    }
  },
  "scale_info": {
    "notation": "1/8\"=1'-0\"",
    "scale_ratio": 96.0,
    "meaning": "1 inch on paper = 96.00 inches in reality",
    "meaning_feet": "1 inch on paper = 8.00 feet in reality"
  },
  "floor_plan_dimensions": {
    "pixels": {
      "width": 1352,
      "height": 2513
    },
    "on_paper_inches": {
      "width": 4.507,
      "height": 8.377
    },
    "real_world": {
      "width": "36'-0.64\"",
      "height": "67'-0.16\"",
      "area_sqft": 2416.05
    }
  },
  "detected_objects": {
    "door": [
      {
        "id": 1,
        "class": "door",
        "confidence": 0.133,
        "bbox_pixels": {
          "x1": 100,
          "y1": 200,
          "x2": 128,
          "y2": 392,
          "width": 28,
          "height": 192
        },
        "measurements": {
          "pixels": {
            "width": 28.8,
            "height": 192.7
          },
          "on_paper_inches": {
            "width": 0.096,
            "height": 0.642
          },
          "real_world": {
            "inches": {
              "width": 9.22,
              "height": 61.67
            },
            "feet_decimal": {
              "width": 0.77,
              "height": 5.14
            },
            "feet_inches": {
              "width": "9.22\"",
              "height": "5'-1.67\""
            }
          }
        },
        "door_measurements": {
          "width_inches": 9.22,
          "height_inches": 61.67,
          "width_feet": 0.77,
          "height_feet": 5.14
        }
      }
    ],
    "wall": [
      {
        "id": 1,
        "class": "wall",
        "confidence": 0.616,
        "bbox_pixels": {
          "x1": 50,
          "y1": 100,
          "x2": 613,
          "y2": 153,
          "width": 563,
          "height": 53
        },
        "measurements": {
          "pixels": {
            "width": 563.9,
            "height": 53.7
          },
          "on_paper_inches": {
            "width": 1.880,
            "height": 0.179
          },
          "real_world": {
            "inches": {
              "width": 180.44,
              "height": 17.19
            },
            "feet_decimal": {
              "width": 15.04,
              "height": 1.43
            },
            "feet_inches": {
              "width": "15'-0.44\"",
              "height": "1'-5.19\""
            }
          }
        },
        "wall_measurements": {
          "length_feet": 15.04,
          "thickness_inches": 17.19
        }
      }
    ]
  },
  "object_counts": {
    "door": 2,
    "wall": 31
  },
  "summary_statistics": {
    "door": {
      "count": 2,
      "average_size_inches": {
        "width": 7.55,
        "height": 60.54
      },
      "range_inches": {
        "width": {
          "min": 5.89,
          "max": 9.22
        },
        "height": {
          "min": 59.41,
          "max": 61.67
        }
      }
    },
    "wall": {
      "count": 31,
      "average_size_inches": {
        "width": 94.60,
        "height": 216.26
      },
      "range_inches": {
        "width": {
          "min": 4.71,
          "max": 370.60
        },
        "height": {
          "min": 5.26,
          "max": 555.51
        }
      },
      "total_wall_length_feet": 773.07
    }
  }
}
```

## Usage

### Frontend (React)

#### Export Button in UI
```tsx
<button onClick={handleExportJSON}>
  <Download /> Export as JSON
</button>
```

#### Export Function
```typescript
const handleExportJSON = () => {
  if (!analysisResult || selectedFloorPlan === null) return
  
  const url = exportFloorPlanJSON(analysisResult.analysis_id, selectedFloorPlan)
  const link = document.createElement('a')
  link.href = url
  link.download = `floor_plan_${selectedFloorPlan}_analysis.json`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
```

### Backend (Python)

#### Generate JSON Programmatically
```python
from app.core.cv.floor_plan_service import get_floor_plan_service

service = get_floor_plan_service()

# After running analysis and detection
analysis_id = "your-analysis-id"
floor_plan_id = 1

# The export endpoint automatically generates the JSON
url = f"/api/floor-plan/export/{analysis_id}/floor-plan/{floor_plan_id}"
```

### Direct API Call

```bash
# Export floor plan analysis
curl -O http://localhost:8000/api/floor-plan/export/{analysis_id}/floor-plan/1

# Export initial analysis (without detections)
curl -O http://localhost:8000/api/floor-plan/export/{analysis_id}
```

## Use Cases

### 1. External Data Processing
Export JSON for processing in:
- Excel/Google Sheets (via JSON import)
- Python pandas DataFrames
- Custom reporting tools
- Database import

### 2. Material Takeoff Integration
Use measurements for:
- Bill of materials generation
- Cost estimation
- Ordering systems
- Project management software

### 3. Archival & Documentation
Save analysis results:
- Project documentation
- Historical records
- Audit trails
- Compliance reports

### 4. Comparison & Analytics
Compare multiple analyses:
- Design iterations
- Different floor plans
- Before/after modifications
- Cross-project analysis

### 5. Third-Party Integration
Feed data to:
- BIM software
- CAD applications
- Estimating software
- Construction management platforms

## File Naming

**Floor Plan Analysis**: `floor_plan_{id}_analysis.json`
**Initial Analysis**: `floor_plan_analysis_{pdf_name}.json`

Files are saved in: `backend/data/uploads/analysis/{analysis_id}/`

## API Response

### Success (200 OK)
Returns downloadable JSON file with:
- `Content-Type: application/json`
- `Content-Disposition: attachment; filename="floor_plan_1_analysis.json"`

### Errors

**404 Not Found**:
```json
{
  "detail": "Analysis {analysis_id} not found"
}
```

**404 Not Found**:
```json
{
  "detail": "Floor plan {floor_plan_id} not found"
}
```

**500 Internal Server Error**:
```json
{
  "detail": "Failed to export floor plan: {error message}"
}
```

## Data Flow

```
1. User completes floor plan analysis
   ↓
2. User detects objects in floor plan
   ↓
3. User clicks "Export as JSON"
   ↓
4. Frontend calls: GET /api/floor-plan/export/{id}/floor-plan/{fp_id}
   ↓
5. Backend retrieves cached results
   ↓
6. Backend generates comprehensive JSON
   ↓
7. Backend saves JSON file
   ↓
8. Backend returns file as download
   ↓
9. Browser downloads JSON file
```

## Benefits

✅ **Complete Data Export**: All measurements, detections, and metadata  
✅ **Machine Readable**: JSON format for easy parsing  
✅ **Human Readable**: Pretty-printed with indentation  
✅ **Comprehensive**: Includes pixels, inches, and feet measurements  
✅ **Organized**: Grouped by object class with statistics  
✅ **Detailed**: Confidence scores, bounding boxes, real dimensions  
✅ **Flexible**: Use in spreadsheets, databases, or custom tools  
✅ **Archival**: Save for future reference or compliance  

## Integration Examples

### Python Processing
```python
import json

# Load exported JSON
with open('floor_plan_1_analysis.json') as f:
    data = json.load(f)

# Extract wall measurements
walls = data['detected_objects']['wall']
total_length = sum(w['wall_measurements']['length_feet'] for w in walls)
print(f"Total wall length: {total_length:.2f} feet")

# Calculate material needs
studs_16_oc = total_length * 0.75  # Approximate
print(f"Studs needed (16\" O.C.): {int(studs_16_oc)}")
```

### Excel Import
1. Open Excel
2. Data → Get Data → From File → From JSON
3. Select downloaded JSON file
4. Transform data as needed
5. Load into worksheet

### Database Import
```sql
-- PostgreSQL example
CREATE TABLE floor_plan_analysis (
    id SERIAL PRIMARY KEY,
    analysis_data JSONB
);

INSERT INTO floor_plan_analysis (analysis_data)
VALUES (pg_read_file('floor_plan_1_analysis.json')::jsonb);

-- Query specific data
SELECT 
    analysis_data->'object_counts'->>'wall' as wall_count,
    analysis_data->'summary_statistics'->'wall'->>'total_wall_length_feet' as total_length
FROM floor_plan_analysis;
```

## Best Practices

1. **Export After Detection**: Always run object detection before exporting for complete data
2. **Save Immediately**: Download and save JSON files after analysis
3. **Verify Scale**: Check that scale was detected correctly before using measurements
4. **Archive Originals**: Keep original PDFs with exported JSON files
5. **Version Control**: Track changes between exports with timestamps
6. **Validate Data**: Verify measurements make sense for your use case

## Future Enhancements

Potential additions:
- [ ] Batch export (multiple floor plans)
- [ ] CSV export format
- [ ] PDF report generation
- [ ] Cloud storage integration
- [ ] Email delivery
- [ ] Comparison reports
- [ ] Custom templates

