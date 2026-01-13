# Pydantic Schema for Gemini Structured Output

## Overview

The code now uses **Pydantic models** to define a strict JSON schema for Gemini's API responses. This ensures type-safe, validated, and reliable data extraction from floor plan images.

## Pydantic Models

### 1. ScaleInfo Model

Defines the structure for scale information extracted from floor plans:

```python
class ScaleInfo(BaseModel):
    """Scale information extracted from floor plan"""
    found: bool = Field(description="Whether a scale was found in the drawing")
    notation: Optional[str] = Field(default=None, description="Exact scale text as shown")
    format: Optional[str] = Field(default=None, description="Format type: imperial_architectural, metric_ratio, or text")
    drawing_unit: Optional[str] = Field(default=None, description="Unit on drawing (e.g., 'inch', 'mm')")
    real_unit: Optional[str] = Field(default=None, description="Real world unit (e.g., 'foot', 'meter')")
    drawing_value: Optional[float] = Field(default=None, description="Numeric value on drawing")
    real_value: Optional[float] = Field(default=None, description="Numeric value in reality")
```

**Fields:**
- `found` (required): Boolean indicating if a scale was detected
- `notation` (optional): The exact scale text as it appears (e.g., "1/4\" = 1'-0\"")
- `format` (optional): Classification of scale format
  - `"imperial_architectural"` - e.g., 1/4" = 1'-0"
  - `"metric_ratio"` - e.g., 1:100
  - `"text"` - other text descriptions
- `drawing_unit` (optional): Unit used on the drawing ("inch", "mm", etc.)
- `real_unit` (optional): Unit in real world ("foot", "meter", etc.)
- `drawing_value` (optional): Numeric value on drawing (e.g., 0.25 for 1/4 inch)
- `real_value` (optional): Numeric value in reality (e.g., 12 for 1 foot in inches)

### 2. FloorPlanAnalysis Model

Defines the complete structure for all floor plan analysis data:

```python
class FloorPlanAnalysis(BaseModel):
    """Complete analysis of a floor plan from Gemini Vision"""
    scale: ScaleInfo = Field(description="Scale information")
    title: Optional[str] = Field(default=None, description="Drawing title or name")
    room_labels: List[str] = Field(default_factory=list, description="List of room names found")
    dimensions: List[str] = Field(default_factory=list, description="List of dimension annotations")
    all_text: List[str] = Field(default_factory=list, description="All other text found in the drawing")
    notes: List[str] = Field(default_factory=list, description="Notes, specifications, or legends")
```

**Fields:**
- `scale` (required): ScaleInfo object containing scale data
- `title` (optional): Drawing title or project name
- `room_labels` (list): Array of room names (e.g., ["Kitchen", "Bedroom"])
- `dimensions` (list): Array of dimension annotations (e.g., ["12'-6\"", "8'-0\""])
- `all_text` (list): All other text found in the image
- `notes` (list): Specifications, notes, or legend text

## How It Works

### 1. Schema Definition

Gemini uses the Pydantic model to understand exactly what JSON structure to return:

```python
response = client.models.generate_content(
    model='gemini-2.0-flash-exp',
    contents=[prompt, image],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=FloorPlanAnalysis  # ← Pydantic model
    )
)
```

### 2. Automatic Validation

When Gemini returns the JSON, it's automatically validated against the schema:

```python
# Parse JSON and validate with Pydantic
data = json.loads(response_text)
validated_data = FloorPlanAnalysis(**data)

# Return as dict
return validated_data.model_dump()
```

### 3. Type Safety

Pydantic ensures:
- ✅ Required fields are present
- ✅ Optional fields have proper defaults
- ✅ Types are correct (bool, str, float, List[str])
- ✅ No unexpected fields
- ✅ Proper validation and error messages

## Example JSON Response

When Gemini analyzes a floor plan, it returns JSON matching this structure:

```json
{
  "scale": {
    "found": true,
    "notation": "1/4\" = 1'-0\"",
    "format": "imperial_architectural",
    "drawing_unit": "inch",
    "real_unit": "foot",
    "drawing_value": 0.25,
    "real_value": 12
  },
  "title": "First Floor Plan",
  "room_labels": [
    "Living Room",
    "Kitchen",
    "Master Bedroom",
    "Bathroom"
  ],
  "dimensions": [
    "12'-6\"",
    "8'-0\"",
    "15'-3\""
  ],
  "all_text": [
    "North Arrow",
    "Sheet 1 of 3",
    "Revision A"
  ],
  "notes": [
    "All dimensions in feet and inches",
    "See specifications for materials"
  ]
}
```

## Benefits of Pydantic Schema

### 1. **Guaranteed Structure**
Gemini must return data matching the exact schema, eliminating parsing errors.

### 2. **Type Validation**
- `found` must be boolean
- `drawing_value` and `real_value` must be numbers
- Lists must contain strings
- Optional fields can be null

### 3. **Default Values**
Missing optional fields automatically get proper defaults:
- `notation: None`
- `room_labels: []`
- `dimensions: []`

### 4. **Error Handling**
If validation fails, get clear error messages about what's wrong:
```python
except Exception as ve:
    print(f"⚠ Validation error: {ve}")
    # Returns fallback structure
```

### 5. **IDE Support**
Full autocomplete and type hints in your IDE:
```python
result = analyze_floor_plan_with_gemini(image)
scale_found = result["scale"]["found"]  # IDE knows this is bool
notation = result["scale"]["notation"]   # IDE knows this is Optional[str]
```

### 6. **Documentation**
Field descriptions are embedded in the model, making the code self-documenting.

## Scale Parsing Examples

### Imperial Architectural Scale

**Input notation**: `"1/4\" = 1'-0\""`

**Gemini returns**:
```json
{
  "found": true,
  "notation": "1/4\" = 1'-0\"",
  "format": "imperial_architectural",
  "drawing_unit": "inch",
  "real_unit": "foot",
  "drawing_value": 0.25,
  "real_value": 12
}
```

**Calculation**:
```
scale_ratio = (real_value * 12) / drawing_value
            = (12) / 0.25
            = 48
```

### Metric Ratio Scale

**Input notation**: `"1:100"`

**Gemini returns**:
```json
{
  "found": true,
  "notation": "1:100",
  "format": "metric_ratio",
  "drawing_unit": "mm",
  "real_unit": "mm",
  "drawing_value": 1.0,
  "real_value": 100.0
}
```

**Calculation**:
```
scale_ratio = real_value / drawing_value
            = 100 / 1
            = 100
```

### No Scale Found

**Gemini returns**:
```json
{
  "found": false,
  "notation": null,
  "format": null,
  "drawing_unit": null,
  "real_unit": null,
  "drawing_value": null,
  "real_value": null
}
```

## Fallback Handling

If Gemini's response is malformed or validation fails:

```python
# Returns safe default structure
FloorPlanAnalysis(
    scale=ScaleInfo(found=False),
    title=None,
    room_labels=[],
    dimensions=[],
    all_text=[],
    notes=[]
).model_dump()
```

## Using the Validated Data

```python
# Analyze floor plan
result = analyze_floor_plan_with_gemini(floor_plan_image)

# Access validated data
if result["scale"]["found"]:
    notation = result["scale"]["notation"]
    drawing_val = result["scale"]["drawing_value"]
    real_val = result["scale"]["real_value"]
    
    print(f"Scale: {notation}")
    print(f"Ratio: {real_val / drawing_val}")

# Access other data
print(f"Title: {result['title']}")
print(f"Rooms: {', '.join(result['room_labels'])}")
print(f"Dimensions found: {len(result['dimensions'])}")
```

## Customizing the Schema

To add new fields, simply extend the Pydantic models:

```python
class ScaleInfo(BaseModel):
    # ...existing fields...
    confidence: Optional[float] = Field(default=None, description="Confidence score for scale detection")
    location: Optional[str] = Field(default=None, description="Where scale was found (e.g., 'title block')")

class FloorPlanAnalysis(BaseModel):
    # ...existing fields...
    date: Optional[str] = Field(default=None, description="Drawing date if shown")
    sheet_number: Optional[str] = Field(default=None, description="Sheet number")
```

Then update the prompt to instruct Gemini to fill these new fields.

## Comparison: Before vs After

### Before (regex parsing)
```python
# Fragile text parsing
scale_match = re.search(r'SCALE:\s*(.+?)(?:\n|$)', response)
if scale_match:
    scale = scale_match.group(1).strip()
    # Still need to parse the scale text...
```

**Problems:**
- ❌ Regex can fail on variations
- ❌ No structure validation
- ❌ Manual parsing required
- ❌ Easy to break

### After (Pydantic schema)
```python
# Structured, validated response
response = client.models.generate_content(
    config=types.GenerateContentConfig(
        response_schema=FloorPlanAnalysis  # Pydantic model
    )
)
validated = FloorPlanAnalysis(**json.loads(response.text))
```

**Benefits:**
- ✅ Guaranteed structure
- ✅ Automatic validation
- ✅ Type safety
- ✅ No parsing needed
- ✅ Self-documenting

## Best Practices

1. **Always validate**: Use Pydantic models for all Gemini responses
2. **Provide good descriptions**: Field descriptions help Gemini understand what to extract
3. **Use Optional wisely**: Mark fields as Optional if they might not be present
4. **Provide examples**: Include examples in the prompt for complex fields
5. **Handle errors**: Always have fallback structures for validation failures
6. **Test variations**: Test with different drawing styles to refine the schema

## Troubleshooting

### Gemini returns incomplete data
- Check field descriptions are clear
- Provide better examples in the prompt
- Make more fields optional if they're hard to detect

### Validation fails
- Check JSON structure in saved files
- Look for type mismatches (string vs number)
- Ensure response matches schema exactly

### Wrong data extracted
- Refine prompt instructions
- Add more specific field descriptions
- Provide format examples

## Summary

Using Pydantic models with Gemini's structured output provides:

✅ **Type-safe** responses with automatic validation  
✅ **Reliable** data extraction with guaranteed structure  
✅ **Clear** contract between Gemini and your code  
✅ **Maintainable** code with self-documenting schemas  
✅ **Error-resistant** with proper fallbacks  

This is the production-ready approach for AI-powered data extraction! 🎯

