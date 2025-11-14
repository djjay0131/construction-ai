"""
File Upload API Endpoints
Handles uploading of architectural drawings
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid
from datetime import datetime
import logging

from app.db.database import get_db
from app.models.project import Drawing, DrawingFormat, Project, ProjectStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def get_file_format(filename: str) -> DrawingFormat:
    """Determine file format from filename."""
    suffix = Path(filename).suffix.lower()
    format_map = {
        '.dwg': DrawingFormat.DWG,
        '.dxf': DrawingFormat.DXF,
        '.pdf': DrawingFormat.PDF,
        '.png': DrawingFormat.PNG,
        '.jpg': DrawingFormat.JPG,
        '.jpeg': DrawingFormat.JPEG,
    }
    if suffix not in format_map:
        raise ValueError(f"Unsupported file format: {suffix}")
    return format_map[suffix]


def validate_file_size(file: UploadFile) -> None:
    """Validate file size."""
    # Note: file.size might be None for some upload types
    # We'll check size during reading
    pass


@router.post("/drawing")
async def upload_drawing(
    file: UploadFile = File(...),
    project_name: str = "Default Project",
    db: Session = Depends(get_db)
):
    """
    Upload an architectural drawing file.

    Args:
        file: The uploaded file (DWG, DXF, PDF, or image)
        project_name: Name of the project (optional)
        db: Database session

    Returns:
        JSON response with drawing ID and metadata
    """
    try:
        # Validate file extension
        try:
            file_format = get_file_format(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        unique_filename = f"{file_id}{file_extension}"

        # Ensure upload directory exists
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = upload_dir / unique_filename
        file_size = 0

        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):  # Read in 8KB chunks
                file_size += len(chunk)

                # Check size limit
                if file_size > settings.MAX_UPLOAD_SIZE:
                    # Clean up partial file
                    file_path.unlink()
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE / (1024*1024):.0f}MB"
                    )

                buffer.write(chunk)

        logger.info(f"Saved uploaded file: {unique_filename} ({file_size} bytes)")

        # Find or create project
        project = db.query(Project).filter(
            Project.name == project_name,
            Project.status == ProjectStatus.ACTIVE
        ).first()

        if not project:
            project = Project(
                name=project_name,
                description=f"Project created for {file.filename}",
                status=ProjectStatus.ACTIVE
            )
            db.add(project)
            db.flush()  # Get project ID

        # Create drawing record
        drawing = Drawing(
            project_id=project.id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_format=file_format,
            file_size_bytes=file_size,
            uploaded_at=datetime.utcnow(),
        )
        db.add(drawing)
        db.commit()
        db.refresh(drawing)

        logger.info(f"Created drawing record: ID={drawing.id}, project_id={project.id}")

        return {
            "success": True,
            "drawing_id": drawing.id,
            "project_id": project.id,
            "filename": file.filename,
            "file_size": file_size,
            "file_format": file_format.value,
            "message": "File uploaded successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)

        # Clean up file if it was created
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink()

        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.get("/drawing/{drawing_id}")
async def get_drawing(drawing_id: int, db: Session = Depends(get_db)):
    """
    Get information about an uploaded drawing.

    Args:
        drawing_id: Drawing ID
        db: Database session

    Returns:
        Drawing information
    """
    drawing = db.query(Drawing).filter(Drawing.id == drawing_id).first()

    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    return {
        "id": drawing.id,
        "project_id": drawing.project_id,
        "filename": drawing.original_filename,
        "file_format": drawing.file_format.value,
        "file_size": drawing.file_size_bytes,
        "uploaded_at": drawing.uploaded_at.isoformat(),
        "metadata": drawing.drawing_metadata,
    }


@router.delete("/drawing/{drawing_id}")
async def delete_drawing(drawing_id: int, db: Session = Depends(get_db)):
    """
    Delete an uploaded drawing.

    Args:
        drawing_id: Drawing ID
        db: Database session

    Returns:
        Success message
    """
    drawing = db.query(Drawing).filter(Drawing.id == drawing_id).first()

    if not drawing:
        raise HTTPException(status_code=404, detail="Drawing not found")

    # Delete file from disk
    file_path = Path(drawing.file_path)
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")

    # Delete database record
    db.delete(drawing)
    db.commit()

    logger.info(f"Deleted drawing: ID={drawing_id}")

    return {"success": True, "message": "Drawing deleted successfully"}
