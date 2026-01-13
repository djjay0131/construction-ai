# Gemini Scale Detection Guide

## Quick Start

The system now uses **Gemini's structured JSON output** to reliably detect architectural scales from floor plans.

## How It Works

### 1. Gemini Analyzes the Image

When you run the code, Gemini:
- Scans the entire floor plan image
- Looks for scale notation in common locations (title blocks, corners, legends)
- Returns structured JSON with parsed scale data

### 2. JSON Response Structure

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
  "room_labels": ["Living Room", "Kitchen"],
  "dimensions": ["12'-6\"", "8'-0\""],
  "all_text": ["various text from drawing"],
  "notes": ["specifications and notes"]
}
```

### 3. Automatic Scale Calculation

The system automatically calculates the scale ratio:

**For Imperial Architectural Scales** (e.g., 1/4" = 1'-0"):
```
scale_ratio = (real_value * 12) / drawing_value
            = (1 * 12) / 0.25
            = 48

Meaning: 1 inch on paper = 48 inches (4 feet) in reality
```

**For Metric Ratio Scales** (e.g., 1:100):
```
scale_ratio = real_value / drawing_value
            = 100 / 1
            = 100

Meaning: 1 unit on paper = 100 units in reality
```

## Supported Scale Formats

### Imperial Architectural
- `1/4" = 1'-0"` (most common)
- `1/8" = 1'-0"`
- `3/32" = 1'-0"`
- `1/16" = 1'-0"`
- `1 inch = 1 foot`
- `Scale: 1/4 inch = 1 foot`

### Metric Ratio
- `1:100`
- `1:50`
- `1:200`
- `1:25`
- `Scale 1:100`

### Text Descriptions
- `Scale: 1/4 inch equals 1 foot`
- `Quarter inch scale`
- Any other text format describing the scale

## Measurement Chain

```
Step 1: Gemini detects scale → Returns JSON with drawing_value and real_value

Step 2: Calculate scale ratio → real_value / drawing_value

Step 3: Convert pixels to paper inches → bbox_pixels / pixels_per_inch

Step 4: Convert paper inches to real inches → paper_inches * scale_ratio

Step 5: Format result → feet-inches notation (e.g., 12'-6")
```

## Common Scales Reference

| Scale Notation | Ratio | 1" on paper = | Use Case |
|---------------|-------|---------------|----------|
| 1/4" = 1'-0" | 48 | 4 feet | Floor plans, site plans |
| 1/8" = 1'-0" | 96 | 8 feet | Building sections |
| 3/32" = 1'-0" | 128 | 10.67 feet | Large buildings |
| 1/16" = 1'-0" | 192 | 16 feet | Site plans |
| 1:100 | 100 | 100 units | Metric plans |
| 1:50 | 50 | 50 units | Detailed metric plans |

## Troubleshooting

### No Scale Detected

If Gemini returns `"found": false`:

1. **Check the drawing** - Is the scale visible in the image?
2. **Check title block** - Scale is often in the title block
3. **Check image quality** - Is the text readable?
4. **Manual override** - You can manually specify the scale in the code

**Manual Override Example:**
```python
# After Gemini analysis, before dimension calculation
if not scale_ratio:
    # Manually set scale (e.g., 1/4" = 1'-0" has ratio 48)
    scale_ratio = 48
    scale_description = "1/4\" = 1'-0\" (manually set)"
```

### Incorrect Scale Detected

If Gemini detects the wrong scale:

1. **Check the JSON output** - Look at the saved `*_gemini.txt` file
2. **Verify notation** - Is it parsing correctly?
3. **Check similar text** - Sometimes notes mention other scales
4. **Use manual override** - Override with correct scale

### Scale in Unusual Format

If your drawings use unusual scale notation:

1. **Check JSON response** - Gemini might still extract the text
2. **Add to parser** - Modify `parse_architectural_scale()` function
3. **Use fallback** - The system will try regex parsing as backup

## Output Files

### Gemini Analysis File
`*_floorplan1_gemini.txt` - Contains the full JSON response:
```json
{
  "scale": {
    "found": true,
    "notation": "1/4\" = 1'-0\"",
    ...
  },
  ...
}
```

### Measurements File
`*_floorplan1_measurements.txt` - Contains calculated dimensions:
```
Scale Information:
  Scale Notation: 1/4" = 1'-0"
  Scale Ratio: 1:48.00
  Meaning: 1 inch on paper = 48.00 inches in reality

Floor Plan Dimensions:
  Real World: 72'-0.00" x 96'-0.00"
  Real World Area: 6912.00 sq ft

WALL (15 detected)
  Wall #1:
    Real Size: 16'-0.00" x 0'-7.20"
    Wall Length: 16.00'
    Wall Thickness: 7.20"
```

## API Key Setup

Make sure you have a `.env` file in the datascience folder:

```bash
GEMINI_API_KEY=your-actual-api-key-here
```

Get your API key from: https://aistudio.google.com/app/apikey

## Best Practices

1. **High-Quality PDFs** - Use 300 DPI when converting PDF to images
2. **Clear Scale Text** - Ensure scale notation is visible and readable
3. **Standard Formats** - Use standard architectural scale notation
4. **Verify Results** - Always check the Gemini JSON output for accuracy
5. **Keep Backups** - Save original PDFs before processing

## Example Usage

```python
# The code automatically:
# 1. Loads PDF and converts to images
# 2. Detects paper size
# 3. Uses Gemini to extract scale (structured JSON)
# 4. Calculates scale ratio
# 5. Measures all objects
# 6. Saves comprehensive reports

# Just run the cell and check the output folder!
```

## What Gets Measured

With the detected scale, you get real-world dimensions for:

- ✅ **Floor plans** - Total width, height, and area
- ✅ **Walls** - Length and thickness
- ✅ **Windows** - Width and height
- ✅ **Doors** - Width and height
- ✅ **Any other objects** - Your YOLO model detects

All measurements are provided in:
- Pixels
- Inches on paper
- Real-world inches
- Real-world feet and inches (architectural notation)
- Decimal feet

## Need Help?

Check these files after running:
1. `*_gemini_analysis.txt` - See what Gemini detected
2. `*_measurements.txt` - See all calculated dimensions
3. Console output - See summary and any warnings

Happy measuring! 📏🏗️

