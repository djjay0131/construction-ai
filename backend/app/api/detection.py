"""
Object Detection API Endpoints
Handles floor plan object detection using computer vision
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import logging
from typing import Dict, Optional

from app.db.database import get_db
from app.core.config import settings
from app.core.cv.detection_service import get_detection_service, DetectionService
from app.schemas.detection import (
    DetectionRequest,
    DetectionResult,
    CalibrationRequest,
    CalibrationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for detection results (for MVP)
# In production, this should be in database or Redis
_detection_cache: Dict[str, tuple] = {}
_annotated_images: Dict[str, bytes] = {}


@router.post("/detect", response_model=DetectionResult)
async def detect_objects(
    file: UploadFile = File(...),
    confidence: float = 0.25,
    selected_labels: Optional[str] = None,
    detection_service: DetectionService = Depends(get_detection_service),
):
    """
    Detect objects in an uploaded floor plan image.

    Args:
        file: Uploaded image file (PNG, JPG, JPEG)
        confidence: Confidence threshold (0-1)
        selected_labels: Comma-separated list of labels to filter for

    Returns:
        Detection results with object list and counts
    """
    try:
        # Validate file type
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in [".png", ".jpg", ".jpeg"]:
            raise HTTPException(
                status_code=400, detail="Only PNG and JPG images are supported"
            )

        # Parse selected labels
        labels_list = None
        if selected_labels:
            labels_list = [label.strip() for label in selected_labels.split(",")]

        # Save uploaded file temporarily
        upload_dir = Path(settings.UPLOAD_DIR) / "detections"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_id = str(uuid.uuid4())
        temp_filename = f"{file_id}{file_extension}"
        temp_path = upload_dir / temp_filename

        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Saved uploaded image: {temp_filename}")

        # Run detection
        detection_result, annotated_image_bytes = detection_service.detect_objects(
            image_path=str(temp_path),
            confidence=confidence,
            selected_labels=labels_list,
        )

        # Cache results
        _detection_cache[detection_result.detection_id] = (detection_result, temp_path)
        _annotated_images[detection_result.detection_id] = annotated_image_bytes

        return detection_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/image/{detection_id}")
async def get_annotated_image(detection_id: str):
    """
    Get the annotated image for a detection result.

    Args:
        detection_id: Detection ID

    Returns:
        PNG image with detected objects annotated
    """
    if detection_id not in _annotated_images:
        raise HTTPException(status_code=404, detail="Annotated image not found")

    image_bytes = _annotated_images[detection_id]

    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.post("/calibrate", response_model=CalibrationResult)
async def calibrate_measurements(
    calibration: CalibrationRequest,
    detection_service: DetectionService = Depends(get_detection_service),
):
    """
    Calibrate object measurements using a reference object.

    Args:
        calibration: Calibration parameters including reference object and size

    Returns:
        Calibrated measurements for all detected objects
    """
    try:
        # Get cached detection result
        if calibration.detection_id not in _detection_cache:
            raise HTTPException(
                status_code=404,
                detail="Detection result not found. Please run detection first.",
            )

        detection_result, _ = _detection_cache[calibration.detection_id]

        # Find reference object
        reference_obj = None
        reference_idx = -1

        for idx, obj in enumerate(detection_result.detected_objects):
            if (
                obj.label == calibration.reference_object_label
                and obj.index == calibration.reference_object_index
            ):
                reference_obj = obj
                reference_idx = idx
                break

        if reference_obj is None:
            raise HTTPException(
                status_code=404,
                detail=f"Reference object not found: {calibration.reference_object_label} {calibration.reference_object_index}",
            )

        # Validate dimension
        if calibration.reference_dimension not in ["width", "height"]:
            raise HTTPException(
                status_code=400,
                detail="reference_dimension must be 'width' or 'height'",
            )

        # Perform calibration
        calibrated_objects, scale_ratio = detection_service.calibrate_measurements(
            detected_objects=detection_result.detected_objects,
            reference_object_index=reference_idx,
            reference_real_size=calibration.reference_real_size,
            reference_dimension=calibration.reference_dimension,
        )

        # Create result
        result = CalibrationResult(
            detection_id=calibration.detection_id,
            scale_ratio=scale_ratio,
            unit=calibration.unit,
            reference_object=f"{calibration.reference_object_label} {calibration.reference_object_index}",
            calibrated_objects=calibrated_objects,
        )

        logger.info(
            f"Calibration complete: scale_ratio={scale_ratio:.6f} {calibration.unit}/pixel"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during calibration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}")


@router.get("/result/{detection_id}", response_model=DetectionResult)
async def get_detection_result(detection_id: str):
    """
    Get a cached detection result.

    Args:
        detection_id: Detection ID

    Returns:
        Detection result
    """
    if detection_id not in _detection_cache:
        raise HTTPException(status_code=404, detail="Detection result not found")

    detection_result, _ = _detection_cache[detection_id]
    return detection_result


@router.delete("/result/{detection_id}")
async def delete_detection_result(detection_id: str):
    """
    Delete a cached detection result and its associated files.

    Args:
        detection_id: Detection ID

    Returns:
        Success message
    """
    if detection_id not in _detection_cache:
        raise HTTPException(status_code=404, detail="Detection result not found")

    # Get file path and delete
    _, temp_path = _detection_cache[detection_id]
    if temp_path.exists():
        temp_path.unlink()
        logger.info(f"Deleted detection file: {temp_path}")

    # Remove from cache
    del _detection_cache[detection_id]
    if detection_id in _annotated_images:
        del _annotated_images[detection_id]

    return {"success": True, "message": "Detection result deleted"}
