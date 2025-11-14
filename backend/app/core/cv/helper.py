import PIL
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import numpy as np
import cv2


def count_detected_objects(model, filtered_boxes):
    """
    Count detected objects and return a dictionary of counts.
    """
    object_counts = {}
    for box in filtered_boxes:
        # Extract class label of detected object
        label = model.names[int(box.cls)]
        # Update count in dictionary
        object_counts[label] = object_counts.get(label, 0) + 1
    return object_counts


def generate_csv(object_counts):
    """
    Generate CSV data from detected object counts.
    """
    csv_data = pd.DataFrame(list(object_counts.items()), columns=["Label", "Count"])
    csv_file = csv_data.to_csv(index=False)
    return csv_file


def extract_wall_measurements(model, filtered_boxes):
    """
    Extract wall objects with their bounding box coordinates and pixel dimensions.
    Returns a list of dictionaries with wall information.
    """
    walls = []
    wall_index = 1

    for box in filtered_boxes:
        label = model.names[int(box.cls)]

        if label == "Wall":
            # Get bounding box coordinates (xyxy format)
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

            # Calculate pixel dimensions
            width_pixels = abs(x2 - x1)
            height_pixels = abs(y2 - y1)

            # Calculate diagonal length (useful for walls at angles)
            diagonal_pixels = np.sqrt(width_pixels**2 + height_pixels**2)

            # Use the longer dimension as the primary measurement
            length_pixels = max(width_pixels, height_pixels)

            wall_info = {
                "index": wall_index,
                "label": label,
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2),
                "width_pixels": float(width_pixels),
                "height_pixels": float(height_pixels),
                "length_pixels": float(length_pixels),
                "diagonal_pixels": float(diagonal_pixels),
                "confidence": float(box.conf[0]),
            }

            walls.append(wall_info)
            wall_index += 1

    return walls


def extract_all_object_measurements(model, filtered_boxes):
    """
    Extract all detected objects with their bounding box coordinates and pixel dimensions.
    Returns a list of dictionaries with object information, numbered by type.
    """
    objects_list = []
    object_counters = {}

    for box in filtered_boxes:
        label = model.names[int(box.cls)]

        # Increment counter for this object type
        if label not in object_counters:
            object_counters[label] = 0
        object_counters[label] += 1

        # Get bounding box coordinates (xyxy format)
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

        # Calculate pixel dimensions
        width_pixels = abs(x2 - x1)
        height_pixels = abs(y2 - y1)

        # Calculate diagonal length
        diagonal_pixels = np.sqrt(width_pixels**2 + height_pixels**2)

        # Use the longer dimension as the primary measurement
        length_pixels = max(width_pixels, height_pixels)

        object_info = {
            "label": label,
            "index": object_counters[label],
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x2),
            "y2": float(y2),
            "width_pixels": float(width_pixels),
            "height_pixels": float(height_pixels),
            "length_pixels": float(length_pixels),
            "diagonal_pixels": float(diagonal_pixels),
            "confidence": float(box.conf[0]),
        }

        objects_list.append(object_info)

    return objects_list


def calculate_real_dimensions_all_objects(
    objects, reference_object_index, reference_real_size, reference_dimension="width"
):
    """
    Calculate real-world dimensions for all objects based on a reference object calibration.

    Args:
        objects: List of object dictionaries with pixel measurements
        reference_object_index: Index in the list of the object used for calibration (0-based)
        reference_real_size: Real-world size of the reference dimension
        reference_dimension: Which dimension to use ('width' or 'height')
                           - 'width' = horizontal span (x-axis)
                           - 'height' = vertical span (y-axis)

    Returns:
        Updated objects list with real-world measurements and the scale ratio
    """
    if (
        not objects
        or reference_object_index < 0
        or reference_object_index >= len(objects)
    ):
        return objects, None

    # Get the reference object
    reference_object = objects[reference_object_index]

    # Get the pixel measurement for the reference dimension
    if reference_dimension == "height":
        reference_pixels = reference_object["height_pixels"]
    else:  # default to width
        reference_pixels = reference_object["width_pixels"]

    # Calculate the scale ratio (real units per pixel)
    scale_ratio = reference_real_size / reference_pixels

    # Apply scale to all objects
    for obj in objects:
        obj["width_real"] = obj["width_pixels"] * scale_ratio
        obj["height_real"] = obj["height_pixels"] * scale_ratio
        # Keep length as max dimension for reference
        obj["length_real"] = obj["length_pixels"] * scale_ratio
        obj["diagonal_real"] = obj["diagonal_pixels"] * scale_ratio

    return objects, scale_ratio


def calculate_real_dimensions(
    walls, reference_wall_index, reference_real_size, reference_dimension="length"
):
    """
    Calculate real-world dimensions for all walls based on a reference wall calibration.

    Args:
        walls: List of wall dictionaries with pixel measurements
        reference_wall_index: Index of the wall used for calibration (1-based)
        reference_real_size: Real-world size of the reference dimension
        reference_dimension: Which dimension to use ('length', 'width', 'height', or 'diagonal')

    Returns:
        Updated walls list with real-world measurements and the scale ratio
    """
    if not walls or reference_wall_index < 1 or reference_wall_index > len(walls):
        return walls, None

    # Get the reference wall (convert to 0-based index)
    reference_wall = walls[reference_wall_index - 1]

    # Get the pixel measurement for the reference dimension
    if reference_dimension == "width":
        reference_pixels = reference_wall["width_pixels"]
    elif reference_dimension == "height":
        reference_pixels = reference_wall["height_pixels"]
    elif reference_dimension == "diagonal":
        reference_pixels = reference_wall["diagonal_pixels"]
    else:  # default to length
        reference_pixels = reference_wall["length_pixels"]

    # Calculate the scale ratio (real units per pixel)
    scale_ratio = reference_real_size / reference_pixels

    # Apply scale to all walls
    for wall in walls:
        wall["width_real"] = wall["width_pixels"] * scale_ratio
        wall["height_real"] = wall["height_pixels"] * scale_ratio
        wall["length_real"] = wall["length_pixels"] * scale_ratio
        wall["diagonal_real"] = wall["diagonal_pixels"] * scale_ratio

    return walls, scale_ratio


def generate_measurements_csv(walls, unit="meters"):
    """
    Generate CSV with wall measurements including real-world dimensions.
    """
    if not walls:
        return "No walls detected"

    data = []
    for wall in walls:
        row = {
            "Wall_ID": f"Wall_{wall['index']}",
            "X1": round(wall["x1"], 2),
            "Y1": round(wall["y1"], 2),
            "X2": round(wall["x2"], 2),
            "Y2": round(wall["y2"], 2),
            "Width_Pixels": round(wall["width_pixels"], 2),
            "Height_Pixels": round(wall["height_pixels"], 2),
            "Length_Pixels": round(wall["length_pixels"], 2),
            "Confidence": round(wall["confidence"], 3),
        }

        # Add real-world dimensions if calculated
        if "width_real" in wall:
            row[f"Width_{unit}"] = round(wall["width_real"], 2)
            row[f"Height_{unit}"] = round(wall["height_real"], 2)
            row[f"Length_{unit}"] = round(wall["length_real"], 2)

        data.append(row)

    csv_data = pd.DataFrame(data)
    csv_file = csv_data.to_csv(index=False)
    return csv_file


def generate_all_measurements_csv(objects, unit="meters"):
    """
    Generate CSV with all object measurements including real-world dimensions.
    """
    if not objects:
        return "No objects detected"

    data = []
    for obj in objects:
        row = {
            "Object_Type": obj["label"],
            "Object_ID": f"{obj['label']}_{obj['index']}",
            "X1": round(obj["x1"], 2),
            "Y1": round(obj["y1"], 2),
            "X2": round(obj["x2"], 2),
            "Y2": round(obj["y2"], 2),
            "Width_Pixels": round(obj["width_pixels"], 2),
            "Height_Pixels": round(obj["height_pixels"], 2),
            "Length_Pixels": round(obj["length_pixels"], 2),
            "Confidence": round(obj["confidence"], 3),
        }

        # Add real-world dimensions if calculated
        if "width_real" in obj:
            row[f"Width_{unit}"] = round(obj["width_real"], 2)
            row[f"Height_{unit}"] = round(obj["height_real"], 2)
            row[f"Length_{unit}"] = round(obj["length_real"], 2)

        data.append(row)

    csv_data = pd.DataFrame(data)
    csv_file = csv_data.to_csv(index=False)
    return csv_file


def plot_with_wall_numbers(result, model, filtered_boxes):
    """
    Plot detection results with numbered labels for all detected objects.

    Args:
        result: YOLO result object
        model: YOLO model
        filtered_boxes: List of filtered detection boxes

    Returns:
        Annotated image as numpy array (RGB format)
    """
    # Get the original image from result
    img = result.orig_img.copy()

    # Convert BGR to RGB if needed
    if len(img.shape) == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Track counters for each object type
    object_counters = {}

    # Draw each box manually with object numbers
    for box in filtered_boxes:
        # Get box coordinates
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

        # Get label and confidence
        cls_id = int(box.cls[0])
        label = model.names[cls_id]
        conf = float(box.conf[0])

        # Increment counter for this object type
        if label not in object_counters:
            object_counters[label] = 0
        object_counters[label] += 1

        # Choose color based on class (use high-contrast vibrant colors)
        # These colors are highly visible on both white and dark backgrounds
        colors = [
            (255, 0, 0),  # Bright Red
            (0, 0, 255),  # Bright Blue
            (255, 0, 255),  # Magenta
            (0, 128, 255),  # Orange-Blue
            (255, 0, 128),  # Pink-Red
            (128, 0, 255),  # Purple
            (0, 255, 128),  # Spring Green
            (255, 128, 0),  # Dark Orange
            (0, 128, 128),  # Teal
            (128, 0, 128),  # Purple
            (192, 0, 192),  # Dark Magenta
        ]
        color = colors[cls_id % len(colors)]

        # Draw bounding box with thicker line for better visibility
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

        # Create label text with number
        label_text = f"{label} {object_counters[label]} ({conf:.2f})"

        # Calculate text size and position - smaller font
        font_scale = 0.4
        font_thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )

        # Draw label background (above the box) with padding
        padding = 3
        label_y = y1 - 10 if y1 - 10 > text_height else y1 + text_height + 10

        # Draw black border around label background for better contrast
        cv2.rectangle(
            img,
            (x1 - 1, label_y - text_height - padding - 1),
            (x1 + text_width + padding + 1, label_y + baseline + 1),
            (0, 0, 0),  # Black border
            2,
        )

        # Draw colored background
        cv2.rectangle(
            img,
            (x1, label_y - text_height - padding),
            (x1 + text_width + padding, label_y + baseline),
            color,
            -1,
        )

        # Draw label text in white with black outline for maximum readability
        # Draw black outline first (thicker for smaller text)
        cv2.putText(
            img,
            label_text,
            (x1 + 2, label_y - 1),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (0, 0, 0),  # Black outline
            font_thickness + 1,
            cv2.LINE_AA,
        )
        # Draw white text on top
        cv2.putText(
            img,
            label_text,
            (x1 + 2, label_y - 1),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),  # White text
            font_thickness,
            cv2.LINE_AA,
        )

    return img
