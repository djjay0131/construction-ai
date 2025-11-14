"""
Pydantic schemas for material takeoff data
Defines the JSON output schema for material lists and cut lists
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class MaterialType(str, Enum):
    """Material type enumeration."""
    LUMBER = "lumber"
    CONCRETE = "concrete"
    DRYWALL = "drywall"
    FASTENER = "fastener"
    TIEDOWN = "tiedown"
    OTHER = "other"


class LumberGrade(str, Enum):
    """Lumber grade enumeration."""
    STUD = "stud"
    NO2 = "no2"
    NO1 = "no1"
    SELECT = "select"


class LumberSpecification(BaseModel):
    """Lumber size specification."""
    nominal_width: int = Field(..., description="Nominal width in inches (e.g., 2 for 2x4)")
    nominal_height: int = Field(..., description="Nominal height in inches (e.g., 4 for 2x4)")
    actual_width: float = Field(..., description="Actual width in inches (e.g., 1.5 for 2x4)")
    actual_height: float = Field(..., description="Actual height in inches (e.g., 3.5 for 2x4)")
    grade: Optional[LumberGrade] = Field(default=LumberGrade.STUD, description="Lumber grade")

    @property
    def size_name(self) -> str:
        """Return lumber size name (e.g., '2x4')."""
        return f"{self.nominal_width}x{self.nominal_height}"


class CutPiece(BaseModel):
    """Individual cut piece from a lumber stock."""
    piece_id: str = Field(..., description="Unique identifier for this piece")
    length_inches: float = Field(..., description="Length of the cut piece in inches")
    label: Optional[str] = Field(None, description="Label/location for this piece (e.g., 'Wall A - Stud #3')")
    description: Optional[str] = Field(None, description="Additional description")


class CutList(BaseModel):
    """Cut list for a specific lumber size from a stock length."""
    stock_length_inches: int = Field(..., description="Stock lumber length in inches (e.g., 96 for 8')")
    pieces: List[CutPiece] = Field(default_factory=list, description="Pieces to cut from this stock")
    waste_inches: float = Field(..., description="Waste from this cut in inches")
    waste_percentage: float = Field(..., description="Waste percentage")
    quantity_needed: int = Field(..., description="Number of this stock length needed")


class MaterialItem(BaseModel):
    """Single material item in the takeoff."""
    material_id: str = Field(..., description="Unique identifier for this material")
    material_type: MaterialType = Field(..., description="Type of material")
    name: str = Field(..., description="Material name (e.g., '2x4 Stud')")
    description: Optional[str] = Field(None, description="Detailed description")
    unit: str = Field(..., description="Unit of measurement (e.g., 'EA', 'LF', 'SF', 'CY')")
    quantity: float = Field(..., description="Quantity needed")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class LumberMaterialItem(MaterialItem):
    """Lumber-specific material item."""
    material_type: MaterialType = Field(default=MaterialType.LUMBER, description="Material type")
    specification: LumberSpecification = Field(..., description="Lumber specifications")
    total_linear_feet: float = Field(..., description="Total linear feet needed")
    cut_lists: Optional[List[CutList]] = Field(None, description="Optimized cut lists")


class MaterialTakeoff(BaseModel):
    """Complete material takeoff result."""
    project_id: Optional[str] = Field(None, description="Associated project ID")
    drawing_filename: str = Field(..., description="Original drawing filename")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")

    # Materials organized by type
    lumber: List[LumberMaterialItem] = Field(default_factory=list, description="Lumber materials")
    concrete: List[MaterialItem] = Field(default_factory=list, description="Concrete materials")
    drywall: List[MaterialItem] = Field(default_factory=list, description="Drywall materials")
    fasteners: List[MaterialItem] = Field(default_factory=list, description="Fastener materials")
    tiedowns: List[MaterialItem] = Field(default_factory=list, description="Tie-down materials")
    other: List[MaterialItem] = Field(default_factory=list, description="Other materials")

    # Summary statistics
    total_items: int = Field(default=0, description="Total number of material items")
    total_waste_percentage: Optional[float] = Field(None, description="Overall waste percentage")

    # Metadata
    confidence_score: Optional[float] = Field(None, description="Overall confidence score (0-1)")
    warnings: List[str] = Field(default_factory=list, description="Warnings or issues encountered")
    notes: List[str] = Field(default_factory=list, description="Additional notes")

    class Config:
        json_schema_extra = {
            "example": {
                "drawing_filename": "HFH_9557_Barnes_Rd.dxf",
                "processed_at": "2024-01-15T10:30:00Z",
                "lumber": [
                    {
                        "material_id": "lumber_001",
                        "material_type": "lumber",
                        "name": "2x4 Stud",
                        "unit": "EA",
                        "quantity": 120,
                        "specification": {
                            "nominal_width": 2,
                            "nominal_height": 4,
                            "actual_width": 1.5,
                            "actual_height": 3.5,
                            "grade": "stud"
                        },
                        "total_linear_feet": 960
                    }
                ],
                "total_items": 1,
                "confidence_score": 0.95
            }
        }


class TakeoffStatus(str, Enum):
    """Takeoff processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TakeoffJob(BaseModel):
    """Takeoff processing job status."""
    job_id: str = Field(..., description="Unique job identifier")
    status: TakeoffStatus = Field(..., description="Current job status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    progress_percentage: Optional[int] = Field(None, description="Progress percentage (0-100)")
    message: Optional[str] = Field(None, description="Status message")
    result: Optional[MaterialTakeoff] = Field(None, description="Takeoff result when completed")
    error: Optional[str] = Field(None, description="Error message if failed")
