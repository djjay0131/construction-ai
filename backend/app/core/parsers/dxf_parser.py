"""
DXF/DWG Parser Module
Parses CAD files using ezdxf to extract geometric elements
"""

import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import Line, LWPolyline, Polyline, Arc, Circle, Text, MText, Insert
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import logging

from .dwg_converter import DWGConverter

logger = logging.getLogger(__name__)


class DXFElement:
    """Represents a parsed DXF element."""

    def __init__(
        self,
        element_type: str,
        layer: str,
        coordinates: List[Tuple[float, float, float]],
        properties: Dict[str, Any] = None
    ):
        self.element_type = element_type
        self.layer = layer
        self.coordinates = coordinates
        self.properties = properties or {}

    def __repr__(self):
        return f"<DXFElement(type={self.element_type}, layer={self.layer}, points={len(self.coordinates)})>"


class WallElement:
    """Represents a wall extracted from DXF."""

    def __init__(
        self,
        start_point: Tuple[float, float],
        end_point: Tuple[float, float],
        thickness: float = 0.0,
        layer: str = "",
        metadata: Dict[str, Any] = None
    ):
        self.start_point = start_point
        self.end_point = end_point
        self.thickness = thickness
        self.layer = layer
        self.metadata = metadata or {}

    @property
    def length(self) -> float:
        """Calculate wall length in drawing units."""
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        return (dx**2 + dy**2)**0.5

    @property
    def length_inches(self) -> float:
        """Get wall length in inches (assuming drawing units are inches)."""
        return self.length

    def __repr__(self):
        return f"<Wall(length={self.length:.2f}, layer={self.layer})>"


class DXFParser:
    """Parser for DXF and DWG files."""

    def __init__(self, file_path: str):
        """
        Initialize DXF parser.

        Args:
            file_path: Path to DXF or DWG file
        """
        self.file_path = Path(file_path)
        self.doc: Optional[Drawing] = None
        self.elements: List[DXFElement] = []
        self.walls: List[WallElement] = []
        self.texts: List[Dict[str, Any]] = []
        self.temp_dxf_path: Optional[Path] = None
        self.converter: Optional[DWGConverter] = None

    def load(self) -> bool:
        """
        Load the DXF/DWG file. DWG files are automatically converted to DXF.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Loading CAD file: {self.file_path}")

            # Handle DWG files - convert to DXF first
            if self.file_path.suffix.lower() == '.dwg':
                logger.info(f"DWG file detected. Converting to DXF: {self.file_path.name}")

                self.converter = DWGConverter()
                success, dxf_path, message = self.converter.convert_to_dxf(self.file_path)

                if not success or dxf_path is None:
                    logger.error(f"Failed to convert DWG to DXF: {message}")
                    return False

                self.temp_dxf_path = dxf_path
                logger.info(f"Successfully converted to temporary DXF: {dxf_path}")

                # Load the converted DXF file
                self.doc = ezdxf.readfile(str(dxf_path))
            else:
                # Load DXF file directly
                self.doc = ezdxf.readfile(str(self.file_path))

            logger.info(f"Successfully loaded {self.file_path.name}")
            return True

        except IOError as e:
            logger.error(f"Failed to load file {self.file_path}: {e}")
            return False
        except ezdxf.DXFStructureError as e:
            logger.error(f"DXF structure error in {self.file_path}: {e}")
            return False

    def get_layers(self) -> List[str]:
        """Get all layer names in the drawing."""
        if not self.doc:
            return []
        return [layer.dxf.name for layer in self.doc.layers]

    def parse_all_entities(self) -> List[DXFElement]:
        """
        Parse all entities in the modelspace.

        Returns:
            List of DXFElement objects
        """
        if not self.doc:
            logger.error("No document loaded")
            return []

        self.elements = []
        msp = self.doc.modelspace()

        for entity in msp:
            element = self._parse_entity(entity)
            if element:
                self.elements.append(element)

        logger.info(f"Parsed {len(self.elements)} elements from {self.file_path.name}")
        return self.elements

    def _parse_entity(self, entity) -> Optional[DXFElement]:
        """Parse a single DXF entity."""
        try:
            layer = entity.dxf.layer if hasattr(entity.dxf, 'layer') else "0"

            if entity.dxftype() == 'LINE':
                return self._parse_line(entity, layer)
            elif entity.dxftype() == 'LWPOLYLINE':
                return self._parse_lwpolyline(entity, layer)
            elif entity.dxftype() == 'POLYLINE':
                return self._parse_polyline(entity, layer)
            elif entity.dxftype() == 'ARC':
                return self._parse_arc(entity, layer)
            elif entity.dxftype() == 'CIRCLE':
                return self._parse_circle(entity, layer)
            elif entity.dxftype() in ['TEXT', 'MTEXT']:
                return self._parse_text(entity, layer)

        except Exception as e:
            logger.warning(f"Failed to parse entity {entity.dxftype()}: {e}")

        return None

    def _parse_line(self, line: Line, layer: str) -> DXFElement:
        """Parse a LINE entity."""
        coords = [
            (line.dxf.start.x, line.dxf.start.y, line.dxf.start.z),
            (line.dxf.end.x, line.dxf.end.y, line.dxf.end.z)
        ]
        return DXFElement("LINE", layer, coords)

    def _parse_lwpolyline(self, poly: LWPolyline, layer: str) -> DXFElement:
        """Parse a LWPOLYLINE entity."""
        coords = [
            (point[0], point[1], 0.0)
            for point in poly.get_points('xy')
        ]
        return DXFElement("LWPOLYLINE", layer, coords, {"closed": poly.closed})

    def _parse_polyline(self, poly: Polyline, layer: str) -> DXFElement:
        """Parse a POLYLINE entity."""
        coords = [
            (vertex.dxf.location.x, vertex.dxf.location.y, vertex.dxf.location.z)
            for vertex in poly.vertices
        ]
        return DXFElement("POLYLINE", layer, coords, {"closed": poly.is_closed})

    def _parse_arc(self, arc: Arc, layer: str) -> DXFElement:
        """Parse an ARC entity."""
        # Sample the arc into line segments
        coords = []
        steps = 16
        import math
        for i in range(steps + 1):
            angle_ratio = i / steps
            angle = math.radians(
                arc.dxf.start_angle + (arc.dxf.end_angle - arc.dxf.start_angle) * angle_ratio
            )
            x = arc.dxf.center.x + arc.dxf.radius * math.cos(angle)
            y = arc.dxf.center.y + arc.dxf.radius * math.sin(angle)
            coords.append((x, y, arc.dxf.center.z))

        return DXFElement("ARC", layer, coords, {"radius": arc.dxf.radius})

    def _parse_circle(self, circle: Circle, layer: str) -> DXFElement:
        """Parse a CIRCLE entity."""
        center = (circle.dxf.center.x, circle.dxf.center.y, circle.dxf.center.z)
        return DXFElement("CIRCLE", layer, [center], {"radius": circle.dxf.radius})

    def _parse_text(self, text, layer: str) -> DXFElement:
        """Parse TEXT or MTEXT entity."""
        content = text.dxf.text if hasattr(text.dxf, 'text') else ""
        insert_point = text.dxf.insert if hasattr(text.dxf, 'insert') else (0, 0, 0)

        coords = [(insert_point.x, insert_point.y, insert_point.z)]
        properties = {"text": content}

        # Store text separately for easier access
        self.texts.append({
            "text": content,
            "position": (insert_point.x, insert_point.y),
            "layer": layer
        })

        return DXFElement("TEXT", layer, coords, properties)

    def extract_walls(self, wall_layers: Optional[List[str]] = None) -> List[WallElement]:
        """
        Extract wall elements from the drawing.

        Args:
            wall_layers: List of layer names to search for walls. If None, search all layers.

        Returns:
            List of WallElement objects
        """
        if not self.elements:
            self.parse_all_entities()

        self.walls = []

        for element in self.elements:
            # Filter by layer if specified
            if wall_layers and element.layer not in wall_layers:
                continue

            # Lines and polylines can represent walls
            if element.element_type == "LINE":
                # Extract 2D coordinates
                start = (element.coordinates[0][0], element.coordinates[0][1])
                end = (element.coordinates[1][0], element.coordinates[1][1])

                wall = WallElement(
                    start_point=start,
                    end_point=end,
                    layer=element.layer,
                    metadata={"element_type": "LINE"}
                )
                self.walls.append(wall)

            elif element.element_type in ["LWPOLYLINE", "POLYLINE"]:
                # Convert polyline segments into individual walls
                coords_2d = [(c[0], c[1]) for c in element.coordinates]

                for i in range(len(coords_2d) - 1):
                    wall = WallElement(
                        start_point=coords_2d[i],
                        end_point=coords_2d[i + 1],
                        layer=element.layer,
                        metadata={"element_type": element.element_type}
                    )
                    self.walls.append(wall)

                # If closed, connect last point to first
                if element.properties.get("closed", False):
                    wall = WallElement(
                        start_point=coords_2d[-1],
                        end_point=coords_2d[0],
                        layer=element.layer,
                        metadata={"element_type": element.element_type, "closing_segment": True}
                    )
                    self.walls.append(wall)

        logger.info(f"Extracted {len(self.walls)} wall elements")
        return self.walls

    def get_drawing_info(self) -> Dict[str, Any]:
        """Get general information about the drawing."""
        if not self.doc:
            return {}

        return {
            "filename": self.file_path.name,
            "dxf_version": self.doc.dxfversion,
            "layers": self.get_layers(),
            "entity_count": len(list(self.doc.modelspace())),
            "units": "inches",  # TODO: Parse actual units from drawing
            "was_converted_from_dwg": self.temp_dxf_path is not None,
        }

    def cleanup(self):
        """Clean up temporary files created during DWG conversion."""
        if self.converter:
            self.converter.cleanup()
            self.converter = None
            self.temp_dxf_path = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup temp files."""
        self.cleanup()
