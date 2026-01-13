"""
Floor Plan Detection Schemas
Pydantic models for floor plan analysis API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ScaleFormat(str, Enum):
    """Scale format types"""
    IMPERIAL_ARCHITECTURAL = "imperial_architectural"
    METRIC_RATIO = "metric_ratio"
    TEXT = "text"
    NOT_FOUND = "not_found"


class ScaleInfo(BaseModel):
    """Scale information extracted from floor plan"""
    found: bool = Field(description="Whether a scale was found in the drawing")
    notation: Optional[str] = Field(default=None, description="Exact scale text as shown")
    format: Optional[str] = Field(default=None, description="Format type")
    drawing_unit: Optional[str] = Field(default=None, description="Unit on drawing")
    real_unit: Optional[str] = Field(default=None, description="Real world unit")
    drawing_value: Optional[float] = Field(default=None, description="Numeric value on drawing")
    real_value: Optional[float] = Field(default=None, description="Numeric value in reality")
    scale_ratio: Optional[float] = Field(default=None, description="Real units / drawing units ratio")


class PaperSize(BaseModel):
    """Paper size information"""
    name: str = Field(description="Paper size name (e.g., 'ARCH D', 'ANSI A')")
    width_inches: float = Field(description="Width in inches")
    height_inches: float = Field(description="Height in inches")
    orientation: str = Field(description="Portrait or Landscape")


class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


class DetectedObject(BaseModel):
    """Detected object in floor plan"""
    id: int = Field(description="Object ID/number")
    class_name: str = Field(description="Object class (wall, door, window, etc.)")
    confidence: float = Field(description="Detection confidence 0-1")
    bbox: BoundingBox = Field(description="Bounding box")
    real_dimensions: Optional[Dict[str, Any]] = Field(default=None, description="Real-world dimensions if scale available")


class FloorPlanInfo(BaseModel):
    """Information about a single detected floor plan"""
    id: int = Field(description="Floor plan number (1-indexed)")
    bbox: BoundingBox = Field(description="Bounding box on page")
    image_url: str = Field(description="URL to cropped floor plan image")
    annotated_image_url: Optional[str] = Field(default=None, description="URL to annotated image with detections")
    numbered_image_url: Optional[str] = Field(default=None, description="URL to numbered annotation image")
    
    # Analysis results
    scale: Optional[ScaleInfo] = Field(default=None, description="Detected scale information")
    detected_objects: List[DetectedObject] = Field(default_factory=list, description="Objects detected in this floor plan")
    object_counts: Dict[str, int] = Field(default_factory=dict, description="Count of each object type")
    
    # OCR results
    ocr_text: Optional[str] = Field(default=None, description="OCR extracted text")
    
    # Dimensions
    width_pixels: int
    height_pixels: int
    width_inches: Optional[float] = None
    height_inches: Optional[float] = None
    real_width: Optional[str] = None  # e.g., "40'-6\""
    real_height: Optional[str] = None
    real_area_sqft: Optional[float] = None


class PDFAnalysisResult(BaseModel):
    """Result of PDF floor plan analysis"""
    analysis_id: str = Field(description="Unique analysis ID")
    filename: str = Field(description="Original filename")
    num_pages: int = Field(description="Number of pages processed")
    
    # Page-level info
    page_number: int = Field(description="Current page number")
    paper_size: PaperSize = Field(description="Detected paper size")
    
    # Floor plans detected on this page
    floor_plans: List[FloorPlanInfo] = Field(description="Floor plans detected on this page")
    num_floor_plans: int = Field(description="Number of floor plans on this page")
    
    # Full page info
    full_page_ocr: Optional[str] = Field(default=None, description="OCR text from full page")
    full_page_scale: Optional[ScaleInfo] = Field(default=None, description="Scale detected from full page")
    
    # Processing status
    processing_time_seconds: float = Field(description="Total processing time")
    warnings: List[str] = Field(default_factory=list, description="Any warnings during processing")


class FloorPlanDetectionRequest(BaseModel):
    """Request for floor plan detection on a specific floor plan"""
    analysis_id: str = Field(description="Analysis ID from initial PDF processing")
    floor_plan_id: int = Field(description="Floor plan ID to analyze")
    confidence: float = Field(default=0.05, ge=0.0, le=1.0, description="Detection confidence threshold")
    manual_scale: Optional[str] = Field(default=None, description="Manual scale override (e.g., '1/4\"=1\\'-0\"')")


class FloorPlanDetectionResult(BaseModel):
    """Result of floor plan object detection"""
    floor_plan_id: int
    detected_objects: List[DetectedObject]
    object_counts: Dict[str, int]
    annotated_image_url: str
    numbered_image_url: str
    scale_used: ScaleInfo
    measurements_summary: Optional[str] = None

