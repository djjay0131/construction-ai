"""
Pydantic schemas for object detection
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class DetectedObject(BaseModel):
    """A single detected object from YOLO"""

    label: str = Field(..., description="Object class label")
    index: int = Field(..., description="Object index within its class")
    x1: float = Field(..., description="Top-left X coordinate")
    y1: float = Field(..., description="Top-left Y coordinate")
    x2: float = Field(..., description="Bottom-right X coordinate")
    y2: float = Field(..., description="Bottom-right Y coordinate")
    width_pixels: float = Field(..., description="Width in pixels")
    height_pixels: float = Field(..., description="Height in pixels")
    length_pixels: float = Field(..., description="Max dimension in pixels")
    diagonal_pixels: float = Field(..., description="Diagonal length in pixels")
    confidence: float = Field(..., description="Detection confidence score")

    # Real-world measurements (populated after calibration)
    width_real: Optional[float] = Field(None, description="Width in real-world units")
    height_real: Optional[float] = Field(None, description="Height in real-world units")
    length_real: Optional[float] = Field(
        None, description="Max dimension in real-world units"
    )
    diagonal_real: Optional[float] = Field(
        None, description="Diagonal in real-world units"
    )


class ObjectCounts(BaseModel):
    """Count of detected objects by type"""

    counts: Dict[str, int] = Field(..., description="Object type to count mapping")


class DetectionResult(BaseModel):
    """Result of object detection on an image"""

    detection_id: str = Field(..., description="Unique detection ID")
    original_filename: str = Field(..., description="Original uploaded filename")
    image_width: int = Field(..., description="Image width in pixels")
    image_height: int = Field(..., description="Image height in pixels")
    detected_objects: List[DetectedObject] = Field(
        ..., description="List of detected objects"
    )
    object_counts: Dict[str, int] = Field(..., description="Count by object type")
    annotated_image_url: str = Field(..., description="URL to annotated image")
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_threshold: float = Field(..., description="Confidence threshold used")
    selected_labels: List[str] = Field(
        ..., description="Object labels that were filtered for"
    )


class DetectionRequest(BaseModel):
    """Request parameters for object detection"""

    confidence: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Confidence threshold"
    )
    selected_labels: List[str] = Field(
        default=[
            "Column",
            "Curtain Wall",
            "Dimension",
            "Door",
            "Railing",
            "Sliding Door",
            "Stair Case",
            "Wall",
            "Window",
        ],
        description="Labels to detect",
    )


class CalibrationRequest(BaseModel):
    """Request to calibrate measurements"""

    detection_id: str = Field(..., description="Detection ID to calibrate")
    reference_object_label: str = Field(
        ..., description="Label of reference object (e.g., 'Wall')"
    )
    reference_object_index: int = Field(..., description="Index of reference object")
    reference_dimension: str = Field(
        ..., description="Which dimension: 'width' or 'height'"
    )
    reference_real_size: float = Field(
        ..., gt=0, description="Real-world size of reference"
    )
    unit: str = Field(default="meters", description="Unit of measurement")


class CalibrationResult(BaseModel):
    """Result of calibration"""

    detection_id: str
    scale_ratio: float = Field(..., description="Real units per pixel")
    unit: str = Field(..., description="Unit of measurement")
    reference_object: str = Field(..., description="Reference object used")
    calibrated_objects: List[DetectedObject] = Field(
        ..., description="Objects with real-world measurements"
    )
