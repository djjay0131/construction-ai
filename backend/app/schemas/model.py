"""
Pydantic schemas for model registry API
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime


class ModelVersionInfo(BaseModel):
    """Information about a specific model version."""
    version: str = Field(..., description="Version identifier")
    gcs_path: str = Field(..., description="Path in GCS bucket")
    gcs_generation: Optional[int] = Field(None, description="GCS object generation for pinning")
    trained_at: Optional[str] = Field(None, description="Training date")
    dataset: Optional[str] = Field(None, description="Training dataset name")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Model metrics")


class ModelSummary(BaseModel):
    """Summary of a registered model."""
    name: str = Field(..., description="Model name")
    description: str = Field("", description="Model description")
    current_version: Optional[str] = Field(None, description="Default version from manifest")
    active_version: Optional[str] = Field(None, description="Currently loaded version")
    available_versions: List[str] = Field(default_factory=list, description="All available versions")


class ModelListResponse(BaseModel):
    """Response for listing all models."""
    models: List[ModelSummary] = Field(..., description="List of registered models")


class ModelStatusResponse(BaseModel):
    """Response for model status endpoint."""
    active_models: Dict[str, str] = Field(..., description="Model name to active version mapping")


class SwapEventResponse(BaseModel):
    """Response representing a swap event."""
    model_name: str = Field(..., description="Model that was swapped")
    from_version: Optional[str] = Field(None, description="Previous version")
    to_version: str = Field(..., description="New version")
    timestamp: datetime = Field(..., description="When the swap was initiated")
    status: str = Field(..., description="Swap status: started, completed, or failed")
    error: Optional[str] = Field(None, description="Error message if failed")


class SwapRequest(BaseModel):
    """Request to hot-swap a model version."""
    version: str = Field(..., description="Target version to swap to")


class SwapHistoryResponse(BaseModel):
    """Response for swap history endpoint."""
    history: List[SwapEventResponse] = Field(default_factory=list, description="Swap event history")
