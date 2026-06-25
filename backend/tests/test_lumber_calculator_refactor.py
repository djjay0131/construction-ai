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


class TestSprint5ProvenanceFields:
    """Sprint 5: source_walls + rule_citations on each BOM line."""

    def test_lumber_item_defaults_provenance_fields_to_empty_lists(self):
        from app.schemas.material import (
            LumberMaterialItem,
            LumberSpecification,
            MaterialType,
        )
        spec = LumberSpecification(
            nominal_width=2, nominal_height=4,
            actual_width=1.5, actual_height=3.5,
            grade=LumberGrade.STUD,
        )
        item = LumberMaterialItem(
            material_id="x", material_type=MaterialType.LUMBER,
            name="2x4 Stud", unit="EA", quantity=1,
            specification=spec, total_linear_feet=1.0,
        )
        assert item.source_walls == []
        assert item.rule_citations == []

    def test_source_walls_populated_for_every_bom_line(self):
        calc = LumberCalculator()
        materials = calc.calculate_all_walls([_wall(120.0), _wall(96.0)])
        assert materials, "expected at least studs + plates"
        for m in materials:
            assert m.source_walls, f"{m.name}: source_walls empty"
            # Synthetic IDs for DXF (no page tag) → wall_0, wall_1
            assert m.source_walls == ["wall_0", "wall_1"]

    def test_source_walls_honor_page_tag_when_present(self):
        """Sprint 4e walls carry metadata['page']; Sprint 5 must use it."""
        from app.core.parsers.dxf_parser import WallElement
        walls = [
            WallElement(
                start_point=(0, 0), end_point=(120, 0),
                metadata={"page": 0, "source": "pdf_raster"},
            ),
            WallElement(
                start_point=(0, 0), end_point=(120, 0),
                metadata={"page": 1, "source": "pdf_raster"},
            ),
        ]
        calc = LumberCalculator()
        materials = calc.calculate_all_walls(walls)
        for m in materials:
            assert m.source_walls == ["page_0/wall_0", "page_1/wall_1"]

    def test_rule_citations_populated_when_kg_client_injected(self):
        class FakeKg:
            def cite_rule_for(self, item):
                return ["R602.3.1"]

        calc = LumberCalculator(kg_client=FakeKg())
        materials = calc.calculate_all_walls([_wall(120.0)])
        for m in materials:
            assert m.rule_citations == ["R602.3.1"]

    def test_rule_citations_empty_when_no_kg_client(self):
        calc = LumberCalculator()
        materials = calc.calculate_all_walls([_wall(120.0)])
        for m in materials:
            assert m.rule_citations == []

    def test_kg_client_receives_each_lumber_item(self):
        seen = []

        class CapturingKg:
            def cite_rule_for(self, item):
                seen.append(item.name)
                return [f"rule_for_{item.name}"]

        calc = LumberCalculator(kg_client=CapturingKg())
        materials = calc.calculate_all_walls([_wall(120.0)])
        # Studs + plates → 2 items, KG called once per item.
        assert len(seen) == len(materials)
        assert seen == [m.name for m in materials]
