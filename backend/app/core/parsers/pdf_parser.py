"""
PDF Parser Module
Parses PDF architectural drawings using PyMuPDF (fitz)
Extracts vector paths and converts them to wall geometry
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PDFWallElement:
    """Represents a wall extracted from PDF."""

    def __init__(
        self,
        start_point: Tuple[float, float],
        end_point: Tuple[float, float],
        page_number: int = 0,
        metadata: Dict[str, Any] = None
    ):
        self.start_point = start_point
        self.end_point = end_point
        self.page_number = page_number
        self.metadata = metadata or {}

    @property
    def length(self) -> float:
        """Calculate wall length in points (PDF units)."""
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        return (dx**2 + dy**2)**0.5

    @property
    def length_inches(self) -> float:
        """
        Get wall length in inches.

        Note: PDF units are in points (1/72 inch).
        This assumes the PDF is at actual scale.
        """
        return self.length / 72.0

    def __repr__(self):
        return f"<PDFWall(length={self.length:.2f}pt, page={self.page_number})>"


class PDFParser:
    """Parser for PDF architectural drawings."""

    def __init__(self, file_path: str):
        """
        Initialize PDF parser.

        Args:
            file_path: Path to PDF file
        """
        self.file_path = Path(file_path)
        self.doc: Optional[fitz.Document] = None
        self.walls: List[PDFWallElement] = []
        self.texts: List[Dict[str, Any]] = []

    def load(self) -> bool:
        """
        Load the PDF file.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Loading PDF file: {self.file_path}")
            self.doc = fitz.open(str(self.file_path))
            logger.info(f"Successfully loaded {self.file_path.name} ({len(self.doc)} pages)")
            return True
        except Exception as e:
            logger.error(f"Failed to load PDF {self.file_path}: {e}")
            return False

    def extract_walls(self, page_numbers: Optional[List[int]] = None) -> List[PDFWallElement]:
        """
        Extract wall elements from PDF pages.

        Args:
            page_numbers: List of page numbers to process (0-indexed). If None, process all pages.

        Returns:
            List of PDFWallElement objects
        """
        if not self.doc:
            logger.error("No document loaded")
            return []

        self.walls = []

        # Determine which pages to process
        if page_numbers is None:
            pages_to_process = range(len(self.doc))
        else:
            pages_to_process = page_numbers

        for page_num in pages_to_process:
            if page_num >= len(self.doc):
                logger.warning(f"Page {page_num} out of range, skipping")
                continue

            page = self.doc[page_num]
            page_walls = self._extract_walls_from_page(page, page_num)
            self.walls.extend(page_walls)

        logger.info(f"Extracted {len(self.walls)} wall elements from {len(pages_to_process)} pages")
        return self.walls

    def _extract_walls_from_page(self, page: fitz.Page, page_num: int) -> List[PDFWallElement]:
        """
        Extract walls from a single PDF page.

        Args:
            page: PyMuPDF Page object
            page_num: Page number

        Returns:
            List of wall elements
        """
        walls = []

        try:
            # Get drawing commands (paths)
            paths = page.get_drawings()

            for path in paths:
                # Each path contains a list of drawing items
                items = path.get("items", [])

                for item in items:
                    # Look for line segments (type "l" = line to)
                    if item[0] == "l":  # Line
                        # item format: ("l", point)
                        # We need to track the current position
                        pass

                # Process path as connected line segments
                if len(items) >= 2:
                    walls.extend(self._convert_path_to_walls(items, page_num))

        except Exception as e:
            logger.warning(f"Error extracting walls from page {page_num}: {e}")

        return walls

    def _convert_path_to_walls(self, items: List[Tuple], page_num: int) -> List[PDFWallElement]:
        """
        Convert PDF path items to wall elements.

        Args:
            items: List of path items (move, line, curve commands)
            page_num: Page number

        Returns:
            List of wall elements
        """
        walls = []
        current_point = None

        for item in items:
            cmd = item[0]

            if cmd == "m":  # Move to
                current_point = item[1]

            elif cmd == "l":  # Line to
                if current_point is not None:
                    end_point = item[1]

                    # Create wall element
                    wall = PDFWallElement(
                        start_point=(current_point.x, current_point.y),
                        end_point=(end_point.x, end_point.y),
                        page_number=page_num,
                        metadata={"type": "line"}
                    )

                    # Filter out very short lines (likely not walls)
                    if wall.length > 5:  # Minimum 5 points (~0.07 inches)
                        walls.append(wall)

                    current_point = end_point

            elif cmd == "c":  # Cubic Bezier curve
                # For now, skip curves (typically not walls)
                # Could approximate with line segments in future
                if current_point is not None:
                    current_point = item[3]  # End point of curve

            elif cmd == "re":  # Rectangle
                # Rectangle format: (x, y, width, height)
                rect = item[1]
                # Create 4 walls for the rectangle
                x, y, w, h = rect.x, rect.y, rect.width, rect.height

                # Convert rectangle to 4 line segments
                rect_walls = [
                    PDFWallElement((x, y), (x + w, y), page_num, {"type": "rectangle", "side": "bottom"}),
                    PDFWallElement((x + w, y), (x + w, y + h), page_num, {"type": "rectangle", "side": "right"}),
                    PDFWallElement((x + w, y + h), (x, y + h), page_num, {"type": "rectangle", "side": "top"}),
                    PDFWallElement((x, y + h), (x, y), page_num, {"type": "rectangle", "side": "left"}),
                ]

                walls.extend([w for w in rect_walls if w.length > 5])

        return walls

    def extract_text(self, page_numbers: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Extract text from PDF pages.

        Args:
            page_numbers: List of page numbers to process. If None, process all pages.

        Returns:
            List of text blocks with positions
        """
        if not self.doc:
            logger.error("No document loaded")
            return []

        self.texts = []

        if page_numbers is None:
            pages_to_process = range(len(self.doc))
        else:
            pages_to_process = page_numbers

        for page_num in pages_to_process:
            if page_num >= len(self.doc):
                continue

            page = self.doc[page_num]

            # Extract text with positions
            text_blocks = page.get_text("dict")["blocks"]

            for block in text_blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        text = " ".join([span["text"] for span in line.get("spans", [])])
                        if text.strip():
                            self.texts.append({
                                "text": text.strip(),
                                "page": page_num,
                                "bbox": line.get("bbox"),
                            })

        logger.info(f"Extracted {len(self.texts)} text blocks")
        return self.texts

    def get_drawing_info(self) -> Dict[str, Any]:
        """Get general information about the PDF."""
        if not self.doc:
            return {}

        return {
            "filename": self.file_path.name,
            "page_count": len(self.doc),
            "format": "PDF",
            "metadata": self.doc.metadata,
            "units": "points (1/72 inch)",
        }

    def close(self):
        """Close the PDF document."""
        if self.doc:
            self.doc.close()
            self.doc = None
