"""
Floor Plan Analysis Service
Handles PDF processing, floor plan detection, scale extraction, and object detection
Based on yolo_train.ipynb workflow
"""

import os
import re
import json
import time
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from PIL import Image
import cv2

# PDF and OCR
from pdf2image import convert_from_path
import easyocr

# YOLO
from ultralytics import YOLO

# Gemini API
try:
    import google.genai as genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from app.core.config import settings
from app.schemas.floor_plan import (
    ScaleInfo, PaperSize, BoundingBox, DetectedObject,
    FloorPlanInfo, PDFAnalysisResult, FloorPlanDetectionResult
)


# Standard architectural paper sizes (width x height in inches)
PAPER_SIZES = {
    'ARCH A': (9, 12),
    'ARCH B': (12, 18),
    'ARCH C': (18, 24),
    'ARCH D': (24, 36),
    'ARCH E': (36, 48),
    'ARCH E1': (30, 42),
    'ANSI A (Letter)': (8.5, 11),
    'ANSI B (Tabloid)': (11, 17),
    'ANSI C': (17, 22),
    'ANSI D': (22, 34),
    'ANSI E': (34, 44),
    'A4': (8.27, 11.69),
    'A3': (11.69, 16.54),
    'A2': (16.54, 23.39),
    'A1': (23.39, 33.11),
    'A0': (33.11, 46.81),
}


class FloorPlanAnalysisService:
    """Service for floor plan detection and analysis"""

    def __init__(self):
        """Initialize models and OCR reader"""
        # Load YOLO models
        self.boundary_model = YOLO(settings.YOLO_BOUNDARY_MODEL_PATH)
        self.object_model = YOLO(settings.YOLO_OBJECT_MODEL_PATH)

        # Initialize EasyOCR
        self.ocr_reader = easyocr.Reader(['en'], gpu=True)

        # Initialize Gemini if available
        self.gemini_client = None
        if GEMINI_AVAILABLE and settings.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Cache for analysis results
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        
        # Cache for detection results (for JSON export)
        self.detection_cache: Dict[str, FloorPlanDetectionResult] = {}

    def detect_paper_size(self, width_px: int, height_px: int, dpi: int = 300) -> PaperSize:
        """Detect paper size from pixel dimensions"""
        width_in = width_px / dpi
        height_in = height_px / dpi

        orientation = "Landscape" if width_in > height_in else "Portrait"
        current_dims = (width_in, height_in)

        # Find closest match (5% tolerance)
        tolerance = 0.05
        best_match = None
        min_error = float('inf')

        for size_name, (std_w, std_h) in PAPER_SIZES.items():
            for dims in [(std_w, std_h), (std_h, std_w)]:
                w_error = abs(current_dims[0] - dims[0]) / dims[0]
                h_error = abs(current_dims[1] - dims[1]) / dims[1]
                total_error = w_error + h_error

                if w_error < tolerance and h_error < tolerance:
                    if total_error < min_error:
                        min_error = total_error
                        best_match = size_name

        if not best_match:
            best_match = f"Custom ({width_in:.1f}\" x {height_in:.1f}\")"

        return PaperSize(
            name=best_match,
            width_inches=width_in,
            height_inches=height_in,
            orientation=orientation
        )

    def analyze_with_gemini(self, image_array: np.ndarray) -> Optional[Dict[str, Any]]:
        """Use Gemini Vision API to extract scale and text information"""
        if not self.gemini_client:
            return None

        try:
            # Convert to PIL Image
            if isinstance(image_array, np.ndarray):
                pil_image = Image.fromarray(image_array)
            else:
                pil_image = image_array

            # Save to bytes
            import io
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            # Create prompt
            prompt = """Analyze this architectural floor plan and extract:

1. SCALE notation (most important!):
   - Imperial: "1/4" = 1'-0"", "1/8" = 1'-0"", etc.
   - Metric: "1:100", "1:50", etc.
   - Look in title block, corners, borders, legends

2. All visible text:
   - Room names and labels
   - Dimension annotations
   - Drawing title
   - Notes and specifications

For scale parsing:
- "1/4" = 1'-0"": drawing_value=0.25, real_value=1.0, drawing_unit="inch", real_unit="foot", format="imperial_architectural"
- "1:100": drawing_value=1, real_value=100, format="metric_ratio"
- If not found: found=false, all fields=null"""

            # Call Gemini
            response = self.gemini_client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=img_byte_arr.getvalue(),
                        mime_type="image/png"
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "scale": {
                                "type": "object",
                                "properties": {
                                    "found": {"type": "boolean"},
                                    "notation": {"type": "string"},
                                    "format": {"type": "string"},
                                    "drawing_unit": {"type": "string"},
                                    "real_unit": {"type": "string"},
                                    "drawing_value": {"type": "number"},
                                    "real_value": {"type": "number"}
                                }
                            },
                            "title": {"type": "string"},
                            "room_labels": {"type": "array", "items": {"type": "string"}},
                            "dimensions": {"type": "array", "items": {"type": "string"}},
                            "all_text": {"type": "array", "items": {"type": "string"}},
                            "notes": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                )
            )

            return json.loads(response.text.strip())

        except Exception as e:
            print(f"Gemini analysis failed: {e}")
            return None

    def extract_scale_info(self, gemini_response: Optional[Dict], manual_scale: Optional[str] = None) -> ScaleInfo:
        """Extract scale information from Gemini response or manual input"""
        # Manual scale takes precedence
        if manual_scale:
            scale_ratio, notation = self.parse_scale_notation(manual_scale)
            if scale_ratio:
                return ScaleInfo(
                    found=True,
                    notation=notation,
                    format="manual",
                    scale_ratio=scale_ratio
                )

        # Try Gemini response
        if gemini_response and isinstance(gemini_response, dict):
            scale_data = gemini_response.get("scale", {})
            if scale_data.get("found", False):
                # Calculate scale ratio
                drawing_value = scale_data.get("drawing_value")
                real_value = scale_data.get("real_value")
                format_type = scale_data.get("format", "")

                scale_ratio = None
                if drawing_value and real_value:
                    if format_type == "imperial_architectural":
                        real_unit = scale_data.get("real_unit", "")
                        if real_unit in ["foot", "feet"]:
                            real_value_inches = real_value * 12
                        else:
                            real_value_inches = real_value
                        scale_ratio = real_value_inches / drawing_value
                    else:
                        scale_ratio = real_value / drawing_value

                return ScaleInfo(
                    found=True,
                    notation=scale_data.get("notation"),
                    format=format_type,
                    drawing_unit=scale_data.get("drawing_unit"),
                    real_unit=scale_data.get("real_unit"),
                    drawing_value=drawing_value,
                    real_value=real_value,
                    scale_ratio=scale_ratio
                )

        return ScaleInfo(found=False)

    def parse_scale_notation(self, scale_string: str) -> Tuple[Optional[float], str]:
        """Parse architectural scale notation"""
        if not scale_string:
            return None, "Not found"

        # Pattern 1: Imperial (e.g., 1/4" = 1'-0")
        pattern1 = r'(\d+)/(\d+)\s*(?:inch|in|")\s*=\s*(\d+)\s*(?:\'|ft|feet)\s*-?\s*(\d*)\s*(?:"|in)?'
        match1 = re.search(pattern1, scale_string, re.IGNORECASE)
        if match1:
            drawing_num = float(match1.group(1))
            drawing_den = float(match1.group(2))
            real_feet = float(match1.group(3))
            real_inches = float(match1.group(4)) if match1.group(4) else 0

            drawing_inches = drawing_num / drawing_den
            real_total_inches = real_feet * 12 + real_inches
            scale_ratio = real_total_inches / drawing_inches

            return scale_ratio, scale_string

        # Pattern 2: Ratio (e.g., 1:100)
        pattern2 = r'1\s*:\s*(\d+(?:\.\d+)?)'
        match2 = re.search(pattern2, scale_string)
        if match2:
            ratio = float(match2.group(1))
            return ratio, scale_string

        return None, scale_string

    def calculate_real_dimensions(self, bbox_w_px: int, bbox_h_px: int,
                                 paper_w_in: float, paper_h_in: float,
                                 page_w_px: int, page_h_px: int,
                                 scale_ratio: Optional[float]) -> Dict[str, Any]:
        """
        Calculate real-world dimensions from pixel measurements.

        The calculation chain:
        1. Paper size (inches) : Page pixels : Floor plan pixels : BBox pixels
        2. Use scale to convert drawing measurements to real-world measurements

        Args:
            bbox_w_px, bbox_h_px: Bounding box dimensions in pixels
            paper_w_in, paper_h_in: Full page paper size in inches
            page_w_px, page_h_px: Full page dimensions in pixels
            scale_ratio: Real world units / drawing units (e.g., 96 for 1/4"=1'-0")

        Returns:
            dict: Dictionary with real-world measurements
        """
        # Step 1: Convert bbox pixels to inches on paper
        # pixels_per_inch for the full page
        ppi_w = page_w_px / paper_w_in
        ppi_h = page_h_px / paper_h_in

        # BBox dimensions in inches on the paper
        bbox_w_in = bbox_w_px / ppi_w
        bbox_h_in = bbox_h_px / ppi_h

        result = {
            'bbox_pixels': (bbox_w_px, bbox_h_px),
            'bbox_inches_on_paper': (bbox_w_in, bbox_h_in),
        }

        # Step 2: Apply scale to get real-world dimensions
        if scale_ratio:
            real_w_in = bbox_w_in * scale_ratio
            real_h_in = bbox_h_in * scale_ratio

            # Convert to feet and inches
            real_width_feet = int(real_w_in // 12)
            real_width_remaining_inches = real_w_in % 12

            real_height_feet = int(real_h_in // 12)
            real_height_remaining_inches = real_h_in % 12

            result['real_inches'] = (real_w_in, real_h_in)
            result['real_feet_inches'] = (
                (real_width_feet, real_width_remaining_inches),
                (real_height_feet, real_height_remaining_inches)
            )
            result['real_feet_decimal'] = (real_w_in / 12, real_h_in / 12)
            result['scale_ratio'] = scale_ratio
        else:
            result['real_inches'] = None
            result['real_feet_inches'] = None
            result['real_feet_decimal'] = None
            result['scale_ratio'] = None
            result['note'] = 'No scale information available'

        return result

    def format_dimension(self, feet: int, inches: float) -> str:
        """Format dimension as architectural notation (e.g., 10'-6\")"""
        if feet == 0:
            return f'{inches:.2f}"'
        else:
            return f"{feet}'-{inches:.2f}\""

    def create_numbered_annotation(self, image: np.ndarray, boxes, class_names: dict) -> np.ndarray:
        """Create annotated image with numbered labels"""
        annotated = image.copy()

        # Class colors
        colors = {
            'wall': (255, 100, 100),
            'window': (100, 255, 100),
            'door': (100, 100, 255),
            'room': (255, 255, 100),
        }

        # Number objects by class
        class_counters = {}

        for idx, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())
            cls = int(box.cls[0].cpu().numpy())
            class_name = class_names[cls]

            # Increment counter
            if class_name not in class_counters:
                class_counters[class_name] = 0
            class_counters[class_name] += 1
            num = class_counters[class_name]

            color = colors.get(class_name.lower(), (100, 255, 255))

            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw label
            label = f"{class_name} #{num}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.rectangle(annotated, (x1, y1 - 25), (x1 + 150, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 5, y1 - 8),
                       font, 0.6, (0, 0, 0), 2, cv2.LINE_AA)

        return annotated

    def process_pdf(self, pdf_path: Path, analysis_id: str, page_num: int = 1) -> PDFAnalysisResult:
        """
        Process a PDF file and detect floor plans

        Args:
            pdf_path: Path to PDF file
            analysis_id: Unique analysis ID
            page_num: Page number to process (1-indexed)

        Returns:
            PDFAnalysisResult with detected floor plans
        """
        start_time = time.time()
        warnings = []

        # Create output directory
        output_dir = Path(settings.UPLOAD_DIR) / "analysis" / analysis_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert PDF to images
        poppler_path = settings.POPPLER_PATH if settings.POPPLER_PATH else None
        pages = convert_from_path(pdf_path, dpi=settings.PDF_DPI, first_page=page_num, last_page=page_num)

        if not pages:
            raise ValueError(f"Could not convert PDF page {page_num}")

        page_img = pages[0]
        page_np = np.array(page_img)

        # Save original page
        page_path = output_dir / f"page{page_num}_original.png"
        page_img.save(page_path)

        # Detect paper size
        img_width, img_height = page_img.size
        paper_size = self.detect_paper_size(img_width, img_height, settings.PDF_DPI)

        # Run OCR on full page
        try:
            ocr_results = self.ocr_reader.readtext(page_np)
            full_page_ocr = '\n'.join([text for _, text, _ in ocr_results])
        except Exception as e:
            full_page_ocr = ""
            warnings.append(f"OCR failed: {str(e)}")

        # Run Gemini analysis on full page
        gemini_response = self.analyze_with_gemini(page_np)
        full_page_scale = self.extract_scale_info(gemini_response)

        # Detect floor plan boundaries
        boundary_results = self.boundary_model.predict(
            source=str(page_path),
            imgsz=640,
            device=0,
            conf=0.80,
            save=False
        )

        detections = boundary_results[0].boxes
        num_floor_plans = len(detections)

        # Process each floor plan
        floor_plans = []

        for idx, box in enumerate(detections):
            fp_id = idx + 1
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())

            # Crop floor plan
            floor_plan_crop = page_np[y1:y2, x1:x2]
            crop_path = output_dir / f"page{page_num}_floorplan{fp_id}.png"
            Image.fromarray(floor_plan_crop).save(crop_path)

            # Floor plan dimensions
            fp_width = x2 - x1
            fp_height = y2 - y1

            # Calculate real dimensions
            dims = self.calculate_real_dimensions(
                fp_width, fp_height,
                paper_size.width_inches, paper_size.height_inches,
                img_width, img_height,
                full_page_scale.scale_ratio if full_page_scale.found else None
            )

            floor_plan_info = FloorPlanInfo(
                id=fp_id,
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf),
                image_url=f"/api/floor-plan/image/{analysis_id}/page{page_num}_floorplan{fp_id}.png",
                width_pixels=fp_width,
                height_pixels=fp_height,
                width_inches=dims['bbox_inches_on_paper'][0],
                height_inches=dims['bbox_inches_on_paper'][1],
                scale=full_page_scale
            )

            if dims.get('real_feet_inches'):
                # Add formatted real dimensions
                w_ft, w_in = dims['real_feet_inches'][0]
                h_ft, h_in = dims['real_feet_inches'][1]
                floor_plan_info.real_width = self.format_dimension(w_ft, w_in)
                floor_plan_info.real_height = self.format_dimension(h_ft, h_in)

            if dims.get('real_feet_decimal'):
                w_ft, h_ft = dims['real_feet_decimal']
                floor_plan_info.real_area_sqft = w_ft * h_ft

            floor_plans.append(floor_plan_info)

        # Cache analysis
        self.analysis_cache[analysis_id] = {
            'pdf_path': str(pdf_path),
            'output_dir': str(output_dir),
            'page_img': page_np,
            'paper_size': paper_size,
            'floor_plans': floor_plans,
            'full_page_scale': full_page_scale
        }

        processing_time = time.time() - start_time

        return PDFAnalysisResult(
            analysis_id=analysis_id,
            filename=pdf_path.name,
            num_pages=1,
            page_number=page_num,
            paper_size=paper_size,
            floor_plans=floor_plans,
            num_floor_plans=num_floor_plans,
            full_page_ocr=full_page_ocr,
            full_page_scale=full_page_scale,
            processing_time_seconds=processing_time,
            warnings=warnings
        )

    def detect_objects_in_floor_plan(self, analysis_id: str, floor_plan_id: int,
                                    confidence: float = 0.05,
                                    manual_scale: Optional[str] = None) -> FloorPlanDetectionResult:
        """
        Detect objects in a specific floor plan

        Args:
            analysis_id: Analysis ID from process_pdf
            floor_plan_id: Floor plan ID (1-indexed)
            confidence: Detection confidence threshold
            manual_scale: Optional manual scale override

        Returns:
            FloorPlanDetectionResult with detected objects
        """
        # Get cached analysis
        if analysis_id not in self.analysis_cache:
            raise ValueError(f"Analysis {analysis_id} not found")

        cache = self.analysis_cache[analysis_id]
        output_dir = Path(cache['output_dir'])

        # Find floor plan
        floor_plan = None
        for fp in cache['floor_plans']:
            if fp.id == floor_plan_id:
                floor_plan = fp
                break

        if not floor_plan:
            raise ValueError(f"Floor plan {floor_plan_id} not found")

        # Get floor plan image path
        crop_path = output_dir / f"page1_floorplan{floor_plan_id}.png"

        # Run object detection
        results = self.object_model.predict(
            source=str(crop_path),
            imgsz=640,
            device=0,
            conf=confidence,
            save=False
        )

        boxes = results[0].boxes
        class_names = self.object_model.names

        # Create numbered annotation
        floor_plan_img = np.array(Image.open(crop_path))
        numbered_annot = self.create_numbered_annotation(floor_plan_img, boxes, class_names)

        # Save numbered annotation
        numbered_path = output_dir / f"page1_floorplan{floor_plan_id}_numbered.png"
        Image.fromarray(numbered_annot).save(numbered_path)

        # Save standard annotation
        standard_annot = results[0].plot()
        standard_annot_rgb = cv2.cvtColor(standard_annot, cv2.COLOR_BGR2RGB)
        standard_path = output_dir / f"page1_floorplan{floor_plan_id}_annotated.png"
        Image.fromarray(standard_annot_rgb).save(standard_path)

        # Extract scale
        scale_info = self.extract_scale_info(None, manual_scale) if manual_scale else floor_plan.scale

        # Process detections
        detected_objects = []
        object_counts = {}
        class_counters = {}

        for idx, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
            conf = float(box.conf[0].cpu().numpy())
            cls = int(box.cls[0].cpu().numpy())
            class_name = class_names[cls]

            # Number objects
            if class_name not in class_counters:
                class_counters[class_name] = 0
            class_counters[class_name] += 1

            # Count objects
            object_counts[class_name] = object_counts.get(class_name, 0) + 1

            obj = DetectedObject(
                id=class_counters[class_name],
                class_name=class_name,
                confidence=conf,
                bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf)
            )

            # Calculate real dimensions if scale available
            if scale_info and scale_info.scale_ratio:
                # Get page dimensions from cache
                page_img_shape = cache['page_img'].shape  # (height, width, channels)
                page_height_px = page_img_shape[0]
                page_width_px = page_img_shape[1]

                dims = self.calculate_real_dimensions(
                    x2 - x1, y2 - y1,
                    cache['paper_size'].width_inches,
                    cache['paper_size'].height_inches,
                    page_width_px,
                    page_height_px,
                    scale_info.scale_ratio
                )
                obj.real_dimensions = dims

            detected_objects.append(obj)

        result = FloorPlanDetectionResult(
            floor_plan_id=floor_plan_id,
            detected_objects=detected_objects,
            object_counts=object_counts,
            annotated_image_url=f"/api/floor-plan/image/{analysis_id}/page1_floorplan{floor_plan_id}_annotated.png",
            numbered_image_url=f"/api/floor-plan/image/{analysis_id}/page1_floorplan{floor_plan_id}_numbered.png",
            scale_used=scale_info
        )
        
        # Cache detection result for JSON export
        cache_key = f"{analysis_id}_fp{floor_plan_id}"
        self.detection_cache[cache_key] = result
        
        return result


# Singleton instance
_service: Optional[FloorPlanAnalysisService] = None


def get_floor_plan_service() -> FloorPlanAnalysisService:
    """Get or create floor plan analysis service singleton"""
    global _service
    if _service is None:
        _service = FloorPlanAnalysisService()
    return _service

