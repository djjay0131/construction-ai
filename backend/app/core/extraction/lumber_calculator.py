"""
Lumber Calculation Module
Calculates lumber quantities for framing based on wall geometry
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math
import logging

from app.core.parsers.dxf_parser import WallElement
from app.schemas.material import (
    LumberMaterialItem,
    LumberSpecification,
    LumberGrade,
    MaterialType,
)

logger = logging.getLogger(__name__)


class StudSpacing(Enum):
    """Standard stud spacing options."""
    OC_16 = 16  # 16 inches on center
    OC_24 = 24  # 24 inches on center
    OC_12 = 12  # 12 inches on center (special cases)


@dataclass
class FramingConfig:
    """Configuration for framing calculations."""
    stud_spacing: StudSpacing = StudSpacing.OC_16
    wall_height_inches: float = 96.0  # Standard 8' ceiling
    include_plates: bool = True  # Top and bottom plates
    include_double_top_plate: bool = True
    include_headers: bool = True  # Headers for door/window openings
    stud_size: Tuple[int, int] = (2, 4)  # 2x4
    plate_size: Tuple[int, int] = (2, 4)  # 2x4


class LumberCalculator:
    """Calculator for lumber material takeoff."""

    # Standard lumber specifications (nominal vs actual dimensions)
    LUMBER_SPECS = {
        (2, 4): LumberSpecification(
            nominal_width=2, nominal_height=4, actual_width=1.5, actual_height=3.5, grade=LumberGrade.STUD
        ),
        (2, 6): LumberSpecification(
            nominal_width=2, nominal_height=6, actual_width=1.5, actual_height=5.5, grade=LumberGrade.STUD
        ),
        (2, 8): LumberSpecification(
            nominal_width=2, nominal_height=8, actual_width=1.5, actual_height=7.25, grade=LumberGrade.STUD
        ),
        (2, 10): LumberSpecification(
            nominal_width=2, nominal_height=10, actual_width=1.5, actual_height=9.25, grade=LumberGrade.STUD
        ),
        (2, 12): LumberSpecification(
            nominal_width=2, nominal_height=12, actual_width=1.5, actual_height=11.25, grade=LumberGrade.STUD
        ),
        (4, 4): LumberSpecification(
            nominal_width=4, nominal_height=4, actual_width=3.5, actual_height=3.5, grade=LumberGrade.NO2
        ),
    }

    def __init__(self, config: Optional[FramingConfig] = None):
        """
        Initialize lumber calculator.

        Args:
            config: Framing configuration
        """
        self.config = config or FramingConfig()

    def calculate_studs_for_wall(self, wall: WallElement) -> int:
        """
        Calculate number of studs needed for a wall.

        Args:
            wall: Wall element

        Returns:
            Number of studs needed

        The calculation follows standard framing practices:
        - One stud at each end
        - Intermediate studs at specified spacing (16" or 24" O.C.)
        """
        wall_length_inches = wall.length_inches
        spacing = self.config.stud_spacing.value

        # Always need 2 studs (one at each end)
        if wall_length_inches <= spacing:
            return 2

        # Calculate number of spaces
        # For 16" O.C.: studs are 16" apart measured from center to center
        num_spaces = math.ceil(wall_length_inches / spacing)

        # Number of studs = number of spaces + 1
        # But we need at least 2 studs
        num_studs = num_spaces + 1

        logger.debug(
            f"Wall length: {wall_length_inches:.2f}\", "
            f"Spacing: {spacing}\", "
            f"Studs: {num_studs}"
        )

        return num_studs

    def calculate_plates_for_wall(self, wall: WallElement) -> Dict[str, float]:
        """
        Calculate plates needed for a wall.

        Args:
            wall: Wall element

        Returns:
            Dictionary with plate types and linear feet needed
        """
        wall_length_feet = wall.length_inches / 12.0

        plates = {}

        if self.config.include_plates:
            # Bottom plate
            plates["bottom_plate"] = wall_length_feet

            # Top plate(s)
            if self.config.include_double_top_plate:
                plates["top_plate_1"] = wall_length_feet
                plates["top_plate_2"] = wall_length_feet
            else:
                plates["top_plate"] = wall_length_feet

        return plates

    def calculate_all_walls(self, walls: List[WallElement]) -> List[LumberMaterialItem]:
        """
        Calculate lumber for all walls.

        Args:
            walls: List of wall elements

        Returns:
            List of lumber material items
        """
        total_studs = 0
        total_plate_length = 0.0

        for wall in walls:
            studs = self.calculate_studs_for_wall(wall)
            total_studs += studs

            plates = self.calculate_plates_for_wall(wall)
            total_plate_length += sum(plates.values())

        # Create material items
        materials: List[LumberMaterialItem] = []

        # Studs
        stud_spec = self.LUMBER_SPECS[self.config.stud_size]
        stud_height_feet = self.config.wall_height_inches / 12.0

        studs_material = LumberMaterialItem(
            material_id="lumber_studs_2x4",
            material_type=MaterialType.LUMBER,
            name=f"{stud_spec.nominal_width}x{stud_spec.nominal_height} Stud",
            description=f"Wall studs @ {self.config.stud_spacing.value}\" O.C., {self.config.wall_height_inches}\" height",
            unit="EA",
            quantity=total_studs,
            specification=stud_spec,
            total_linear_feet=total_studs * stud_height_feet,
            metadata={
                "height_inches": self.config.wall_height_inches,
                "spacing": self.config.stud_spacing.value,
            }
        )
        materials.append(studs_material)

        # Plates
        if total_plate_length > 0:
            plate_spec = self.LUMBER_SPECS[self.config.plate_size]

            # Count number of plates
            num_plate_runs = 1  # bottom plate
            if self.config.include_double_top_plate:
                num_plate_runs += 2  # two top plates
            else:
                num_plate_runs += 1  # one top plate

            plates_material = LumberMaterialItem(
                material_id="lumber_plates_2x4",
                material_type=MaterialType.LUMBER,
                name=f"{plate_spec.nominal_width}x{plate_spec.nominal_height} Plate",
                description=f"Top and bottom plates ({num_plate_runs} runs)",
                unit="LF",
                quantity=math.ceil(total_plate_length),
                specification=plate_spec,
                total_linear_feet=total_plate_length,
                metadata={
                    "num_runs": num_plate_runs,
                    "double_top_plate": self.config.include_double_top_plate,
                }
            )
            materials.append(plates_material)

        logger.info(
            f"Calculated lumber for {len(walls)} walls: "
            f"{total_studs} studs, {total_plate_length:.2f} LF of plates"
        )

        return materials

    def calculate_total_linear_feet(self, walls: List[WallElement]) -> float:
        """
        Calculate total linear feet of walls.

        Args:
            walls: List of wall elements

        Returns:
            Total linear feet
        """
        total_inches = sum(wall.length_inches for wall in walls)
        return total_inches / 12.0

    def get_summary_stats(self, walls: List[WallElement]) -> Dict[str, any]:
        """
        Get summary statistics for framing.

        Args:
            walls: List of wall elements

        Returns:
            Dictionary of statistics
        """
        total_studs = sum(self.calculate_studs_for_wall(wall) for wall in walls)
        total_linear_feet = self.calculate_total_linear_feet(walls)

        plates = {}
        for wall in walls:
            wall_plates = self.calculate_plates_for_wall(wall)
            for plate_type, length in wall_plates.items():
                plates[plate_type] = plates.get(plate_type, 0.0) + length

        return {
            "num_walls": len(walls),
            "total_linear_feet": total_linear_feet,
            "total_studs": total_studs,
            "plates": plates,
            "stud_spacing": self.config.stud_spacing.value,
            "wall_height": self.config.wall_height_inches,
        }
