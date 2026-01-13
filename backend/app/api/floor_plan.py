"""
Floor Plan Analysis API Endpoints
Handles PDF upload, floor plan detection, scale extraction, and object detection
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import uuid
import logging
import time
import json
from typing import Optional

from app.core.config import settings
from app.core.cv.floor_plan_service import get_floor_plan_service, FloorPlanAnalysisService
from app.schemas.floor_plan import (
    PDFAnalysisResult,
    FloorPlanDetectionRequest,
    FloorPlanDetectionResult
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze-pdf", response_model=PDFAnalysisResult)
async def analyze_pdf(
    file: UploadFile = File(...),
    page_number: int = Query(1, ge=1, description="Page number to process"),
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Upload and analyze a PDF to detect floor plans, scale, and paper size.

    This is the first step in the workflow. It will:
    1. Convert the PDF page to an image
    2. Detect paper size (ARCH D, ANSI A, etc.)
    3. Run OCR on the full page
    4. Use Gemini to extract scale information
    5. Detect floor plan boundaries using YOLO
    6. Return metadata about each detected floor plan

    The user can then select which floor plan(s) to analyze further.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Save uploaded file
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = upload_dir / f"{analysis_id}.pdf"

        with open(pdf_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Processing PDF: {file.filename} (analysis_id={analysis_id})")

        # Process PDF
        result = service.process_pdf(pdf_path, analysis_id, page_number)

        logger.info(f"Analysis complete: {result.num_floor_plans} floor plan(s) detected")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/detect-objects", response_model=FloorPlanDetectionResult)
async def detect_objects_in_floor_plan(
    request: FloorPlanDetectionRequest,
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Detect objects (walls, doors, windows) in a specific floor plan.

    This is the second step in the workflow. After the user selects a floor plan
    from the analyze-pdf results, call this endpoint to:
    1. Run YOLO object detection on the selected floor plan
    2. Extract detailed measurements using the detected scale
    3. Return annotated images with numbered objects
    4. Return object counts and dimensions

    Args:
        request: Contains analysis_id, floor_plan_id, confidence threshold, and optional manual scale

    Returns:
        Detection results with annotated images and measurements
    """
    try:
        logger.info(f"Detecting objects: analysis={request.analysis_id}, floor_plan={request.floor_plan_id}, conf={request.confidence}")

        result = service.detect_objects_in_floor_plan(
            request.analysis_id,
            request.floor_plan_id,
            request.confidence,
            request.manual_scale
        )

        logger.info(f"Detection complete: {len(result.detected_objects)} objects detected")

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting objects: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/image/{analysis_id}/{filename}")
async def get_analysis_image(analysis_id: str, filename: str):
    """
    Get an image from an analysis (original, annotated, or numbered).

    Args:
        analysis_id: The analysis ID
        filename: The image filename (e.g., "page1_floorplan1.png")

    Returns:
        The image file
    """
    try:
        image_path = Path(settings.UPLOAD_DIR) / "analysis" / analysis_id / filename

        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(
            image_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve image")


@router.get("/status/{analysis_id}")
async def get_analysis_status(
    analysis_id: str,
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Get the status of an analysis.

    Returns information about whether the analysis exists and what floor plans
    have been detected.
    """
    if analysis_id in service.analysis_cache:
        cache = service.analysis_cache[analysis_id]
        return {
            "exists": True,
            "num_floor_plans": len(cache['floor_plans']),
            "floor_plan_ids": [fp.id for fp in cache['floor_plans']]
        }
    else:
        return {"exists": False}


@router.delete("/analysis/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Delete an analysis and its associated files.

    Cleans up cached data and removes generated images.
    """
    try:
        # Remove from cache
        if analysis_id in service.analysis_cache:
            del service.analysis_cache[analysis_id]

        # Delete files
        analysis_dir = Path(settings.UPLOAD_DIR) / "analysis" / analysis_id
        pdf_file = Path(settings.UPLOAD_DIR) / f"{analysis_id}.pdf"

        if analysis_dir.exists():
            import shutil
            shutil.rmtree(analysis_dir)

        if pdf_file.exists():
            pdf_file.unlink()

        return {"success": True, "message": "Analysis deleted"}

    except Exception as e:
        logger.error(f"Error deleting analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete analysis")


@router.get("/export/{analysis_id}")
async def export_analysis_json(
    analysis_id: str,
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Export complete analysis results as a JSON file.

    Includes all detected floor plans, objects, measurements, and metadata.
    Returns a downloadable JSON file.
    """
    try:
        # Get cached analysis
        if analysis_id not in service.analysis_cache:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

        cache = service.analysis_cache[analysis_id]

        # Build comprehensive JSON report
        report = {
            "analysis_id": analysis_id,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "document": {
                "filename": Path(cache['pdf_path']).name,
                "paper_size": {
                    "name": cache['paper_size'].name,
                    "width_inches": cache['paper_size'].width_inches,
                    "height_inches": cache['paper_size'].height_inches,
                    "orientation": cache['paper_size'].orientation
                },
                "resolution": {
                    "dpi": 300,
                    "width_pixels": cache['page_img'].shape[1],
                    "height_pixels": cache['page_img'].shape[0]
                }
            },
            "scale": None,
            "floor_plans": []
        }

        # Add scale information
        if cache['full_page_scale'] and cache['full_page_scale'].found:
            report["scale"] = {
                "found": True,
                "notation": cache['full_page_scale'].notation,
                "format": cache['full_page_scale'].format,
                "scale_ratio": cache['full_page_scale'].scale_ratio,
                "drawing_unit": cache['full_page_scale'].drawing_unit,
                "real_unit": cache['full_page_scale'].real_unit,
                "drawing_value": cache['full_page_scale'].drawing_value,
                "real_value": cache['full_page_scale'].real_value
            }

        # Add floor plans
        for fp in cache['floor_plans']:
            floor_plan_data = {
                "id": fp.id,
                "bbox": {
                    "x1": fp.bbox.x1,
                    "y1": fp.bbox.y1,
                    "x2": fp.bbox.x2,
                    "y2": fp.bbox.y2,
                    "confidence": fp.bbox.confidence
                },
                "dimensions": {
                    "pixels": {
                        "width": fp.width_pixels,
                        "height": fp.height_pixels
                    },
                    "on_paper_inches": {
                        "width": fp.width_inches,
                        "height": fp.height_inches
                    },
                    "real_world": {
                        "width": fp.real_width,
                        "height": fp.real_height,
                        "area_sqft": fp.real_area_sqft
                    }
                },
                "detected_objects": [],
                "object_counts": {},
                "statistics": {}
            }

            report["floor_plans"].append(floor_plan_data)

        # Save JSON file
        output_dir = Path(settings.UPLOAD_DIR) / "analysis" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"analysis_report_{analysis_id}.json"

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated JSON report: {json_path}")

        # Return as downloadable file
        return FileResponse(
            json_path,
            media_type="application/json",
            filename=f"floor_plan_analysis_{Path(cache['pdf_path']).stem}.json",
            headers={"Content-Disposition": f"attachment; filename=floor_plan_analysis_{Path(cache['pdf_path']).stem}.json"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting JSON: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export analysis: {str(e)}")


@router.get("/export/{analysis_id}/floor-plan/{floor_plan_id}")
async def export_floor_plan_json(
    analysis_id: str,
    floor_plan_id: int,
    service: FloorPlanAnalysisService = Depends(get_floor_plan_service)
):
    """
    Export detailed floor plan analysis with object detections as JSON.

    Includes all detected objects with measurements, statistics, and metadata.
    This should be called after running object detection on a floor plan.
    """
    try:
        # Get cached analysis
        if analysis_id not in service.analysis_cache:
            raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

        cache = service.analysis_cache[analysis_id]

        # Find the floor plan
        floor_plan = None
        for fp in cache['floor_plans']:
            if fp.id == floor_plan_id:
                floor_plan = fp
                break

        if not floor_plan:
            raise HTTPException(status_code=404, detail=f"Floor plan {floor_plan_id} not found")
        
        # Build detailed report structure FIRST
        report = {
            "analysis_id": analysis_id,
            "floor_plan_id": floor_plan_id,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "document_info": {
                "filename": Path(cache['pdf_path']).name,
                "paper_size": cache['paper_size'].name,
                "paper_dimensions_inches": {
                    "width": cache['paper_size'].width_inches,
                    "height": cache['paper_size'].height_inches
                },
                "page_resolution_pixels": {
                    "width": cache['page_img'].shape[1],
                    "height": cache['page_img'].shape[0]
                },
                "dpi": 300,
                "pixels_per_inch": {
                    "width": cache['page_img'].shape[1] / cache['paper_size'].width_inches,
                    "height": cache['page_img'].shape[0] / cache['paper_size'].height_inches
                }
            },
            "scale_info": None,
            "floor_plan_dimensions": {
                "pixels": {
                    "width": floor_plan.width_pixels,
                    "height": floor_plan.height_pixels
                },
                "on_paper_inches": {
                    "width": floor_plan.width_inches,
                    "height": floor_plan.height_inches
                },
                "real_world": {
                    "width": floor_plan.real_width,
                    "height": floor_plan.real_height,
                    "area_sqft": floor_plan.real_area_sqft
                }
            },
            "detected_objects": {},
            "object_counts": {},
            "summary_statistics": {}
        }
        
        # Add scale information
        if floor_plan.scale and floor_plan.scale.found:
            report["scale_info"] = {
                "notation": floor_plan.scale.notation,
                "scale_ratio": floor_plan.scale.scale_ratio,
                "meaning": f"1 inch on paper = {floor_plan.scale.scale_ratio:.2f} inches in reality" if floor_plan.scale.scale_ratio else None,
                "meaning_feet": f"1 inch on paper = {floor_plan.scale.scale_ratio/12:.2f} feet in reality" if floor_plan.scale.scale_ratio else None
            }
        
        # Check if detection results exist
        detection_cache_key = f"{analysis_id}_fp{floor_plan_id}"
        detection_result = service.detection_cache.get(detection_cache_key)
        
        if detection_result:
            # Add detected objects
            report["object_counts"] = detection_result.object_counts

            # Group objects by class
            objects_by_class = {}
            for obj in detection_result.detected_objects:
                if obj.class_name not in objects_by_class:
                    objects_by_class[obj.class_name] = []

                obj_data = {
                    "id": obj.id,
                    "class": obj.class_name,
                    "confidence": obj.confidence,
                    "bbox_pixels": {
                        "x1": obj.bbox.x1,
                        "y1": obj.bbox.y1,
                        "x2": obj.bbox.x2,
                        "y2": obj.bbox.y2,
                        "width": obj.bbox.x2 - obj.bbox.x1,
                        "height": obj.bbox.y2 - obj.bbox.y1
                    }
                }

                if obj.real_dimensions:
                    dims = obj.real_dimensions
                    obj_data["measurements"] = {
                        "pixels": {
                            "width": dims.get('bbox_pixels', [0, 0])[0],
                            "height": dims.get('bbox_pixels', [0, 0])[1]
                        },
                        "on_paper_inches": {
                            "width": dims.get('bbox_inches_on_paper', [0, 0])[0],
                            "height": dims.get('bbox_inches_on_paper', [0, 0])[1]
                        }
                    }

                    if dims.get('real_inches'):
                        obj_data["measurements"]["real_world"] = {
                            "inches": {
                                "width": dims['real_inches'][0],
                                "height": dims['real_inches'][1]
                            },
                            "feet_decimal": {
                                "width": dims.get('real_feet_decimal', [0, 0])[0],
                                "height": dims.get('real_feet_decimal', [0, 0])[1]
                            }
                        }

                        if dims.get('real_feet_inches'):
                            w_ft, w_in = dims['real_feet_inches'][0]
                            h_ft, h_in = dims['real_feet_inches'][1]
                            obj_data["measurements"]["real_world"]["feet_inches"] = {
                                "width": f"{w_ft}'-{w_in:.2f}\"" if w_ft > 0 else f"{w_in:.2f}\"",
                                "height": f"{h_ft}'-{h_in:.2f}\"" if h_ft > 0 else f"{h_in:.2f}\""
                            }

                        # Add class-specific measurements
                        if obj.class_name.lower() == 'door':
                            obj_data["door_measurements"] = {
                                "width_inches": dims['real_inches'][0],
                                "height_inches": dims['real_inches'][1],
                                "width_feet": dims['real_inches'][0] / 12,
                                "height_feet": dims['real_inches'][1] / 12
                            }
                        elif obj.class_name.lower() == 'wall':
                            length = max(dims.get('real_feet_decimal', [0, 0]))
                            thickness = min(dims.get('real_inches', [0, 0]))
                            obj_data["wall_measurements"] = {
                                "length_feet": length,
                                "thickness_inches": thickness
                            }
                        elif obj.class_name.lower() == 'window':
                            obj_data["window_measurements"] = {
                                "width_inches": dims['real_inches'][0],
                                "height_inches": dims['real_inches'][1]
                            }

                objects_by_class[obj.class_name].append(obj_data)

            report["detected_objects"] = objects_by_class

            # Calculate summary statistics
            for class_name, objects in objects_by_class.items():
                if objects and objects[0].get("measurements", {}).get("real_world"):
                    widths = [obj["measurements"]["real_world"]["inches"]["width"] for obj in objects if "measurements" in obj and "real_world" in obj["measurements"]]
                    heights = [obj["measurements"]["real_world"]["inches"]["height"] for obj in objects if "measurements" in obj and "real_world" in obj["measurements"]]

                    if widths and heights:
                        stats = {
                            "count": len(objects),
                            "average_size_inches": {
                                "width": sum(widths) / len(widths),
                                "height": sum(heights) / len(heights)
                            },
                            "range_inches": {
                                "width": {"min": min(widths), "max": max(widths)},
                                "height": {"min": min(heights), "max": max(heights)}
                            }
                        }

                        # For walls, add total length
                        if class_name.lower() == 'wall':
                            lengths = [obj.get("wall_measurements", {}).get("length_feet", 0) for obj in objects if "wall_measurements" in obj]
                            if lengths:
                                stats["total_wall_length_feet"] = sum(lengths)

                        report["summary_statistics"][class_name] = stats
        else:
            report["note"] = "Object detection has not been run for this floor plan yet"
        
        # Save JSON file
        output_dir = Path(settings.UPLOAD_DIR) / "analysis" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"floor_plan_{floor_plan_id}_report.json"

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated detailed floor plan JSON: {json_path}")

        # Return as downloadable file
        return FileResponse(
            json_path,
            media_type="application/json",
            filename=f"floor_plan_{floor_plan_id}_analysis.json",
            headers={"Content-Disposition": f"attachment; filename=floor_plan_{floor_plan_id}_analysis.json"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting floor plan JSON: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to export floor plan: {str(e)}")

