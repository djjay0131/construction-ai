"""
Material Takeoff API Endpoints
Processes architectural drawings and generates material takeoffs
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging
import traceback

from app.db.database import get_db
from app.models.project import Drawing, MaterialTakeoffRecord, TakeoffStatus
from app.schemas.material import MaterialTakeoff, TakeoffJob
from app.core.parsers.dxf_parser import DXFParser
from app.core.extraction.lumber_calculator import LumberCalculator, FramingConfig, StudSpacing

logger = logging.getLogger(__name__)

router = APIRouter()


def process_drawing_takeoff(
    drawing_id: int,
    db: Session,
    wall_height: float = 96.0,
    stud_spacing: int = 16
) -> MaterialTakeoff:
    """
    Process a drawing and generate material takeoff.

    Args:
        drawing_id: ID of the drawing to process
        db: Database session
        wall_height: Wall height in inches (default 96" = 8')
        stud_spacing: Stud spacing in inches (default 16" O.C.)

    Returns:
        MaterialTakeoff object
    """
    # Get drawing from database
    drawing = db.query(Drawing).filter(Drawing.id == drawing_id).first()
    if not drawing:
        raise ValueError(f"Drawing {drawing_id} not found")

    # Get or create takeoff record
    takeoff_record = db.query(MaterialTakeoffRecord).filter(
        MaterialTakeoffRecord.drawing_id == drawing_id
    ).first()

    if not takeoff_record:
        takeoff_record = MaterialTakeoffRecord(
            project_id=drawing.project_id,
            drawing_id=drawing_id,
            status=TakeoffStatus.PENDING
        )
        db.add(takeoff_record)
        db.commit()
        db.refresh(takeoff_record)

    # Update status to processing
    takeoff_record.status = TakeoffStatus.PROCESSING
    takeoff_record.started_at = datetime.utcnow()
    db.commit()

    try:
        logger.info(f"Processing drawing: {drawing.original_filename}")

        # Check if file format is supported
        if drawing.file_format.value == 'dwg':
            error_msg = (
                "DWG files are not yet supported in Phase 1 MVP. "
                "Please convert your DWG file to DXF format using: "
                "LibreCAD, FreeCAD, or an online converter like CloudConvert. "
                "DXF support is fully functional!"
            )
            raise ValueError(error_msg)

        # Parse the DXF file
        parser = DXFParser(drawing.file_path)

        if not parser.load():
            raise Exception(f"Failed to load {drawing.file_format.value.upper()} file. Please ensure the file is a valid DXF format.")

        # Get drawing info
        drawing_info = parser.get_drawing_info()
        logger.info(f"Drawing info: {drawing_info}")

        # Extract walls
        # TODO: Intelligently determine which layers contain walls
        # For now, extract from all layers
        walls = parser.extract_walls()

        if not walls:
            logger.warning("No walls found in drawing")

        # Configure framing calculation
        spacing_enum = StudSpacing.OC_16 if stud_spacing == 16 else StudSpacing.OC_24
        framing_config = FramingConfig(
            stud_spacing=spacing_enum,
            wall_height_inches=wall_height,
            include_plates=True,
            include_double_top_plate=True,
        )

        # Calculate lumber
        calculator = LumberCalculator(framing_config)
        lumber_materials = calculator.calculate_all_walls(walls)

        # Get summary stats
        stats = calculator.get_summary_stats(walls)

        # Create MaterialTakeoff result
        takeoff = MaterialTakeoff(
            project_id=str(drawing.project_id),
            drawing_filename=drawing.original_filename,
            processed_at=datetime.utcnow(),
            lumber=lumber_materials,
            total_items=len(lumber_materials),
            notes=[
                f"Processed {len(walls)} wall elements",
                f"Total wall length: {stats['total_linear_feet']:.2f} linear feet",
                f"Stud spacing: {stud_spacing}\" O.C.",
                f"Wall height: {wall_height}\"",
            ]
        )

        # Update takeoff record
        takeoff_record.status = TakeoffStatus.COMPLETED
        takeoff_record.completed_at = datetime.utcnow()
        takeoff_record.processing_time_seconds = (
            takeoff_record.completed_at - takeoff_record.started_at
        ).total_seconds()
        takeoff_record.result_data = takeoff.model_dump(mode='json')
        takeoff_record.total_items = takeoff.total_items
        takeoff_record.processing_metadata = {
            "method": "rule_based",
            "wall_count": len(walls),
            "stats": stats,
        }

        db.commit()

        logger.info(f"Takeoff completed: {takeoff.total_items} items in {takeoff_record.processing_time_seconds:.2f}s")

        return takeoff

    except Exception as e:
        logger.error(f"Error processing takeoff: {e}", exc_info=True)

        # Update record with error
        takeoff_record.status = TakeoffStatus.FAILED
        takeoff_record.error_message = str(e)
        takeoff_record.completed_at = datetime.utcnow()
        db.commit()

        raise


@router.post("/process/{drawing_id}")
async def create_takeoff(
    drawing_id: int,
    wall_height: Optional[float] = 96.0,
    stud_spacing: Optional[int] = 16,
    db: Session = Depends(get_db)
):
    """
    Create a material takeoff for a drawing.

    Args:
        drawing_id: ID of the uploaded drawing
        wall_height: Wall height in inches (default 96")
        stud_spacing: Stud spacing in inches - 16 or 24 (default 16)
        db: Database session

    Returns:
        Material takeoff result
    """
    # Validate stud spacing
    if stud_spacing not in [12, 16, 24]:
        raise HTTPException(
            status_code=400,
            detail="Stud spacing must be 12, 16, or 24 inches"
        )

    # Check if drawing exists
    drawing = db.query(Drawing).filter(Drawing.id == drawing_id).first()
    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    # Check if file format is supported for processing
    if drawing.file_format.value not in ['dwg', 'dxf']:
        raise HTTPException(
            status_code=400,
            detail=f"Processing not yet supported for {drawing.file_format.value} files. Currently only DWG/DXF are supported."
        )

    try:
        # Process the takeoff
        result = process_drawing_takeoff(
            drawing_id=drawing_id,
            db=db,
            wall_height=wall_height,
            stud_spacing=stud_spacing
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating takeoff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process takeoff: {str(e)}")


@router.get("/result/{drawing_id}")
async def get_takeoff_result(
    drawing_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the material takeoff result for a drawing.

    Args:
        drawing_id: ID of the drawing
        db: Database session

    Returns:
        Material takeoff result or job status
    """
    # Get the most recent takeoff for this drawing
    takeoff_record = db.query(MaterialTakeoffRecord).filter(
        MaterialTakeoffRecord.drawing_id == drawing_id
    ).order_by(MaterialTakeoffRecord.started_at.desc()).first()

    if not takeoff_record:
        raise HTTPException(status_code=404, detail="No takeoff found for this drawing")

    # Return result based on status
    if takeoff_record.status == TakeoffStatus.COMPLETED:
        return takeoff_record.result_data

    elif takeoff_record.status == TakeoffStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail=f"Takeoff processing failed: {takeoff_record.error_message}"
        )

    else:
        # Pending or processing
        return {
            "status": takeoff_record.status.value,
            "message": f"Takeoff is {takeoff_record.status.value}",
            "started_at": takeoff_record.started_at.isoformat() if takeoff_record.started_at else None
        }


@router.get("/status/{drawing_id}")
async def get_takeoff_status(
    drawing_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the processing status of a takeoff.

    Args:
        drawing_id: ID of the drawing
        db: Database session

    Returns:
        Processing status
    """
    takeoff_record = db.query(MaterialTakeoffRecord).filter(
        MaterialTakeoffRecord.drawing_id == drawing_id
    ).order_by(MaterialTakeoffRecord.started_at.desc()).first()

    if not takeoff_record:
        return {"status": "not_started", "message": "No takeoff has been initiated for this drawing"}

    return {
        "status": takeoff_record.status.value,
        "started_at": takeoff_record.started_at.isoformat() if takeoff_record.started_at else None,
        "completed_at": takeoff_record.completed_at.isoformat() if takeoff_record.completed_at else None,
        "processing_time_seconds": takeoff_record.processing_time_seconds,
        "total_items": takeoff_record.total_items,
        "error_message": takeoff_record.error_message,
    }
