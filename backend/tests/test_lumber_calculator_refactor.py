"""Tests for the Sprint 2a LumberCalculator refactor (AC-5, AC-4 parity).

Covers:
* The class-level ``LUMBER_SPECS`` attribute is gone.
* Constructor accepts a ``lumber_specs`` dict and uses it.
* When the dict is omitted, the calculator falls back to
  ``DEFAULT_LUMBER_SPECS`` and produces the same result as the pre-refactor
  hardcoded set (AC-4 round-trip parity).
"""

from app.core.extraction.lumber_calculator import (
    DEFAULT_LUMBER_SPECS,
    FramingConfig,
    LumberCalculator,
    StudSpacing,
)
from app.core.parsers.dxf_parser import WallElement
from app.schemas.material import LumberGrade, LumberSpecification


def _wall(length_inches: float) -> WallElement:
    """Helper: build a WallElement whose .length_inches matches the input."""
    return WallElement(
        start_point=(0.0, 0.0),
        end_point=(length_inches, 0.0),
        thickness=4.0,
        layer="A-WALL",
    )


class TestRefactorContract:
    def test_class_no_longer_exposes_hardcoded_specs(self):
        assert not hasattr(LumberCalculator, "LUMBER_SPECS"), (
            "LumberCalculator.LUMBER_SPECS must be removed; specs come from the KG-loaded dict"
        )

    def test_constructor_accepts_lumber_specs_dict(self):
        custom = {
            (2, 4): LumberSpecification(
                nominal_width=2, nominal_height=4,
                actual_width=1.5, actual_height=3.5,
                grade=LumberGrade.STUD,
            )
        }
        calc = LumberCalculator(lumber_specs=custom)
        assert calc.lumber_specs is custom

    def test_falls_back_to_default_when_dict_omitted(self):
        calc = LumberCalculator()
        assert calc.lumber_specs is DEFAULT_LUMBER_SPECS


class TestDefaultParity:
    """AC-4: round-trip parity — DEFAULT must reproduce pre-refactor results."""

    def test_default_specs_have_expected_six_keys(self):
        assert set(DEFAULT_LUMBER_SPECS.keys()) == {
            (2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (4, 4),
        }

    def test_2x4_default_matches_known_actual_dims(self):
        spec = DEFAULT_LUMBER_SPECS[(2, 4)]
        assert spec.actual_width == 1.5
        assert spec.actual_height == 3.5
        assert spec.grade == LumberGrade.STUD

    def test_4x4_default_is_no2_grade(self):
        spec = DEFAULT_LUMBER_SPECS[(4, 4)]
        assert spec.actual_width == 3.5
        assert spec.actual_height == 3.5
        assert spec.grade == LumberGrade.NO2


class TestCalculateAllWallsUsesInjectedSpecs:
    def test_uses_injected_dict_not_defaults(self):
        """Inject a single (2,4) entry with a *distinct* description so we
        can prove the calculator pulled from the injected dict, not DEFAULT."""
        marker = LumberSpecification(
            nominal_width=2, nominal_height=4,
            actual_width=1.5, actual_height=3.5,
            grade=LumberGrade.STUD,
        )
        injected = {(2, 4): marker}
        config = FramingConfig(stud_size=(2, 4), include_plates=False, stud_spacing=StudSpacing.OC_16)
        calc = LumberCalculator(config=config, lumber_specs=injected)

        materials = calc.calculate_all_walls([_wall(120.0)])
        assert len(materials) == 1
        # The materials use specification = marker (same object)
        assert materials[0].specification is marker
