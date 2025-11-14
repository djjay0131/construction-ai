"""
YOLO Detection Service
Handles floor plan object detection using YOLOv8
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import uuid
from datetime import datetime
import cv2
import numpy as np
from PIL import Image
import base64
from io import BytesIO

from ultralytics import YOLO
import torch

from app.schemas.detection import DetectedObject, DetectionResult
from app.core.cv import helper

logger = logging.getLogger(__name__)

# Fix for PyTorch 2.6+ weights_only=True default
# Only apply if the function exists (PyTorch 2.6+)
if hasattr(torch.serialization, "add_safe_globals"):
    try:
        from ultralytics.nn.modules.conv import Conv
        from ultralytics.nn.tasks import DetectionModel

        torch.serialization.add_safe_globals([Conv, DetectionModel, YOLO])
    except Exception as e:
        logger.warning(f"Could not add safe globals for PyTorch serialization: {e}")


class DetectionService:
    """Service for object detection using YOLO"""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize detection service with YOLO model.

        Args:
            model_path: Path to YOLO weights file (default: best.pt in cv folder)
        """
        if model_path is None:
            # Default to best.pt in the same directory
            current_dir = Path(__file__).parent
            model_path = str(current_dir / "best.pt")

        self.model_path = model_path
        self.model: Optional[YOLO] = None
        self._load_model()

        # Available labels
        self.available_labels = [
            "Column",
            "Curtain Wall",
            "Dimension",
            "Door",
            "Railing",
            "Sliding Door",
            "Stair Case",
            "Wall",
            "Window",
        ]

    def _load_model(self):
        """Load YOLO model"""
        try:
            logger.info(f"Loading YOLO model from {self.model_path}")
            self.model = YOLO(self.model_path)
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect_objects(
        self,
        image_path: str,
        confidence: float = 0.25,
        selected_labels: Optional[List[str]] = None,
    ) -> Tuple[DetectionResult, bytes]:
        """
        Detect objects in an image.

        Args:
            image_path: Path to the image file
            confidence: Confidence threshold (0-1)
            selected_labels: List of labels to filter for

        Returns:
            Tuple of (DetectionResult, annotated_image_bytes)
        """
        if self.model is None:
            raise RuntimeError("YOLO model not loaded")

        if selected_labels is None:
            selected_labels = self.available_labels

        try:
            # Load image
            uploaded_image = Image.open(image_path)
            image_width, image_height = uploaded_image.size

            # Run detection
            results = self.model.predict(uploaded_image, conf=confidence)
            result = results[0]

            # Filter boxes by selected labels
            filtered_boxes = [
                box
                for box in result.boxes
                if self.model.names[int(box.cls)] in selected_labels
            ]
            result.boxes = filtered_boxes

            # Extract object measurements
            detected_objects_list = helper.extract_all_object_measurements(
                self.model, filtered_boxes
            )

            # Convert to Pydantic models
            detected_objects = [DetectedObject(**obj) for obj in detected_objects_list]

            # Count objects
            object_counts = helper.count_detected_objects(self.model, filtered_boxes)

            # Generate annotated image
            annotated_image = helper.plot_with_wall_numbers(
                result, self.model, filtered_boxes
            )

            # Convert annotated image to bytes
            annotated_image_rgb = cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(annotated_image_rgb)
            img_byte_arr = BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            annotated_image_bytes = img_byte_arr.getvalue()

            # Create detection result
            detection_id = str(uuid.uuid4())
            original_filename = Path(image_path).name

            detection_result = DetectionResult(
                detection_id=detection_id,
                original_filename=original_filename,
                image_width=image_width,
                image_height=image_height,
                detected_objects=detected_objects,
                object_counts=object_counts,
                annotated_image_url=f"/api/detection/image/{detection_id}",
                confidence_threshold=confidence,
                selected_labels=selected_labels,
            )

            logger.info(
                f"Detection complete: {len(detected_objects)} objects found "
                f"in {original_filename}"
            )

            return detection_result, annotated_image_bytes

        except Exception as e:
            logger.error(f"Error during detection: {e}")
            raise

    def calibrate_measurements(
        self,
        detected_objects: List[DetectedObject],
        reference_object_index: int,
        reference_real_size: float,
        reference_dimension: str = "width",
    ) -> Tuple[List[DetectedObject], float]:
        """
        Calibrate measurements based on a reference object.

        Args:
            detected_objects: List of detected objects
            reference_object_index: Index in list for reference object
            reference_real_size: Real-world size of reference dimension
            reference_dimension: Which dimension to use ('width' or 'height')

        Returns:
            Tuple of (calibrated_objects, scale_ratio)
        """
        # Convert to dict format for helper function
        objects_dict = [obj.model_dump() for obj in detected_objects]

        # Calculate real dimensions
        calibrated_objects_dict, scale_ratio = (
            helper.calculate_real_dimensions_all_objects(
                objects_dict,
                reference_object_index,
                reference_real_size,
                reference_dimension,
            )
        )

        # Convert back to Pydantic models
        calibrated_objects = [DetectedObject(**obj) for obj in calibrated_objects_dict]

        return calibrated_objects, scale_ratio


# Global service instance
_detection_service: Optional[DetectionService] = None


def get_detection_service() -> DetectionService:
    """Get or create detection service instance"""
    global _detection_service
    if _detection_service is None:
        _detection_service = DetectionService()
    return _detection_service
