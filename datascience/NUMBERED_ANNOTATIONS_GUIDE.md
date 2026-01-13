# Numbered Object Annotations

## Overview

The floor plan analysis now creates **numbered annotations** on the PNG images, with each detected object (wall, window, door, etc.) labeled with a unique number that corresponds directly to the measurements in the text file.

## What Was Added

### 1. **Numbered Annotation Function**

A new function `create_numbered_annotation()` that:
- Assigns sequential numbers to each object within its class
- Draws color-coded bounding boxes
- Adds numbered labels (e.g., "Wall #1", "Window #3")
- Displays confidence scores
- Uses consistent numbering across images and measurement files

### 2. **Color-Coded Classes**

Each object type has a distinct color:
- 🔴 **Walls**: Light Red `(255, 100, 100)`
- 🟢 **Windows**: Light Green `(100, 255, 100)`
- 🔵 **Doors**: Light Blue `(100, 100, 255)`
- 🟡 **Rooms**: Yellow `(255, 255, 100)`
- 🔷 **Other**: Cyan `(100, 255, 255)`

### 3. **Two Annotation Styles**

For each floor plan, you get TWO annotated images:

#### Standard YOLO Annotation
- File: `*_floorplan{N}_objects.png`
- Default YOLO visualization
- All objects shown with class names

#### Numbered Annotation (NEW!)
- File: `*_floorplan{N}_objects_numbered.png`
- Custom visualization with numbered labels
- Each object labeled: "Wall #12", "Door #3", etc.
- Matches measurement file numbering exactly

## Example Output

### Annotated Image
```
┌─────────────────────────────────────────────┐
│                                             │
│   ┌──────────────┐                         │
│   │  Wall #1     │    ┌──────┐             │
│   │  0.95        │    │Window│             │
│   └──────────────┘    │  #1  │             │
│                       │ 0.87 │             │
│   ┌──────────────┐    └──────┘             │
│   │  Wall #2     │                         │
│   │  0.92        │    ┌─────┐              │
│   └──────────────┘    │Door │              │
│                       │ #1  │              │
│   ┌──────────────┐    │0.91 │              │
│   │  Wall #3     │    └─────┘              │
│   │  0.89        │                         │
│   └──────────────┘                         │
└─────────────────────────────────────────────┘
```

Each box shows:
- **Top label**: Class name and number (e.g., "Wall #12")
- **Bottom label**: Confidence score (e.g., "0.95")
- **Color**: Class-specific color for easy identification

### Measurement File

The measurement file references the numbered image:

```
=============================================================
Detected Objects: 45
=============================================================

NOTE: Object numbers correspond to labels in the annotated image:
      example_page1_floorplan1_objects_numbered.png

WALL (15 detected)
------------------------------------------------------------

  Wall #1:
    Confidence: 0.923
    Pixels: 1200.0 x 45.0 px
    On Paper: 4.00" x 0.15"
    Real Size: 16'-0.00" x 0'-7.20"
    Wall Length: 16.00'
    Wall Thickness: 7.20"

  Wall #2:
    Confidence: 0.918
    Pixels: 980.0 x 42.0 px
    On Paper: 3.27" x 0.14"
    Real Size: 13'-1.20" x 0'-6.72"
    Wall Length: 13.09'
    Wall Thickness: 6.72"

  Wall #3:
    Confidence: 0.892
    Pixels: 1450.0 x 48.0 px
    On Paper: 4.83" x 0.16"
    Real Size: 19'-4.00" x 0'-7.68"
    Wall Length: 19.33'
    Wall Thickness: 7.68"

WINDOW (8 detected)
------------------------------------------------------------

  Window #1:
    Confidence: 0.885
    Pixels: 180.0 x 120.0 px
    On Paper: 0.60" x 0.40"
    Real Size: 2'-4.80" x 1'-7.20"
    Window Width: 28.80" (2.40')
    Window Height: 19.20" (1.60')

  Window #2:
    Confidence: 0.878
    Pixels: 190.0 x 125.0 px
    On Paper: 0.63" x 0.42"
    Real Size: 2'-6.24" x 1'-8.00"
    Window Width: 30.24" (2.52')
    Window Height: 20.00" (1.67')

DOOR (3 detected)
------------------------------------------------------------

  Door #1:
    Confidence: 0.912
    Pixels: 210.0 x 90.0 px
    On Paper: 0.70" x 0.30"
    Real Size: 2'-9.60" x 1'-2.40"
    Door Width: 33.60" (2.80')
    Door Height: 14.40" (1.20')
```

## How It Works

### Step 1: Object Detection
```python
# YOLO detects objects in the floor plan
object_results = object_model.predict(floor_plan_image)
```

### Step 2: Group by Class
```python
# Group objects by class for consistent numbering
objects_by_class = {
    'wall': [0, 2, 5, 8, ...],    # Indices of wall detections
    'window': [1, 3, 4, ...],      # Indices of window detections
    'door': [6, 7, ...]            # Indices of door detections
}
```

### Step 3: Assign Numbers
```python
# Each class gets sequential numbering
Wall #1, Wall #2, Wall #3, ...
Window #1, Window #2, Window #3, ...
Door #1, Door #2, Door #3, ...
```

### Step 4: Create Annotation
```python
# Draw numbered labels on image
numbered_annot = create_numbered_annotation(
    image=floor_plan_crop,
    detection_boxes=object_results[0].boxes,
    class_names=object_model.names,
    objects_by_class=objects_by_class
)
```

### Step 5: Save and Reference
```python
# Save numbered image
save(numbered_annot, "*_objects_numbered.png")

# Reference in measurement file
f.write("NOTE: Object numbers correspond to labels in the annotated image:\n")
f.write("      example_page1_floorplan1_objects_numbered.png\n\n")
```

## Label Format

Each label on the image contains:

```
┌─────────────────┐
│  Wall #12       │  ← Class name + number (white text on colored background)
└─────────────────┘
      0.95          ← Confidence score (colored text)
```

- **Background color**: Matches object class color
- **Text color**: Black for visibility
- **Font**: OpenCV's HERSHEY_SIMPLEX
- **Position**: Above bounding box (or below if at top edge)

## Use Cases

### 1. **Material Takeoff**
Look at image, identify "Wall #12", check measurement file for exact dimensions.

### 2. **Quality Control**
Verify that "Window #3" in the image matches the specification.

### 3. **Communication**
Tell contractors: "Window #5 needs to be 3'-0\" wide (currently shown as 2'-9\")"

### 4. **Documentation**
Create reports that reference specific objects by number.

### 5. **Verification**
Cross-check detected objects against architectural drawings.

## File Naming Convention

For a PDF named `example.pdf`, page 1, floor plan 1:

| File | Description |
|------|-------------|
| `example_page1_floorplan1.png` | Cropped floor plan |
| `example_page1_floorplan1_objects.png` | Standard YOLO annotation |
| `example_page1_floorplan1_objects_numbered.png` | **Numbered annotation** ⭐ |
| `example_page1_floorplan1_measurements.txt` | Measurements file (references numbered image) |
| `example_page1_floorplan1_ocr.txt` | OCR text |
| `example_page1_floorplan1_gemini.txt` | Gemini analysis |

## Customization

### Change Colors

Edit the `class_colors` dictionary in `create_numbered_annotation()`:

```python
class_colors = {
    'wall': (255, 0, 0),      # Pure red
    'window': (0, 255, 0),     # Pure green
    'door': (0, 0, 255),       # Pure blue
    'room': (255, 255, 0),     # Yellow
}
```

### Change Label Format

Modify the label text:

```python
# Current format
label = f"{obj_class_name} #{obj_number}"

# Alternatives
label = f"{obj_class_name}_{obj_number}"  # Wall_12
label = f"{obj_number}"                    # Just the number
label = f"{obj_class_name[0]}{obj_number}" # W12 (first letter + number)
```

### Change Font Size

Adjust font scale and thickness:

```python
font_scale = 0.8        # Larger labels
thickness = 3           # Thicker text

font_scale = 0.4        # Smaller labels
thickness = 1           # Thinner text
```

### Add Dimensions to Labels

Show measurements directly on the image:

```python
# Add to label
if obj_dims['real_inches']:
    w_ft, w_in = obj_dims['real_feet_inches'][0]
    label = f"{obj_class_name} #{obj_number}: {w_ft}'-{w_in:.0f}\""
```

## Benefits

✅ **Easy Reference** - Quickly locate specific objects  
✅ **Clear Communication** - Reference objects by number in discussions  
✅ **Quality Assurance** - Verify measurements against visual inspection  
✅ **Documentation** - Create detailed reports with object references  
✅ **Training Data** - Review and correct detections by number  
✅ **Material Ordering** - Match quantities to specific locations  

## Example Workflow

1. **Open numbered image**: `example_page1_floorplan1_objects_numbered.png`
2. **Identify object**: See "Wall #12" in the image
3. **Open measurements**: `example_page1_floorplan1_measurements.txt`
4. **Find Wall #12**: Search for "Wall #12:"
5. **Read dimensions**: Wall Length: 16.00', Wall Thickness: 7.20"
6. **Use the data**: Order materials, verify compliance, etc.

## Tips

- **Print the image**: Large format prints with numbered labels for field reference
- **Compare versions**: Use numbered and standard annotations together
- **Zoom in**: Labels remain readable when zoomed
- **Color coding**: Quickly identify object types by color
- **Sequential numbering**: Objects numbered in detection order within each class

## Summary

The numbered annotation feature provides a **direct visual-to-data correspondence**, making it easy to:
- Reference specific objects
- Verify measurements
- Communicate with teams
- Create detailed reports
- Ensure quality control

Each object on the image has a unique number that matches exactly with its entry in the measurement file! 📊🔢

