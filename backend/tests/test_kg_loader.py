"""Unit tests for ``app.core.kg.loader.load_lumber_specs``.

The loader translates Neo4j records into the application's
``LumberSpecification`` schema. We exercise that translation with a
MagicMock session — full round-trip against a real DB is covered in
``test_kg_integration.py``.
"""

from unittest.mock import MagicMock

from app.core.kg.loader import load_lumber_specs
from app.schemas.material import LumberGrade


def _fake_node(width, height, actual_w, actual_h, grade):
    node = {
        "nominal_width": width,
        "nominal_height": height,
        "actual_width": actual_w,
        "actual_height": actual_h,
        "grade": grade,
    }
    return node


def test_returns_empty_dict_when_no_active_nodes():
    session = MagicMock()
    session.run.return_value = iter([])
    specs = load_lumber_specs(session)
    assert specs == {}


def test_translates_one_record_to_typed_specification():
    session = MagicMock()
    record = {"l": _fake_node(2, 4, 1.5, 3.5, "stud")}
    session.run.return_value = iter([record])

    specs = load_lumber_specs(session)
    assert (2, 4) in specs
    spec = specs[(2, 4)]
    assert spec.nominal_width == 2
    assert spec.nominal_height == 4
    assert spec.actual_width == 1.5
    assert spec.actual_height == 3.5
    assert spec.grade == LumberGrade.STUD


def test_translates_multiple_records_keyed_by_nominal_dims():
    session = MagicMock()
    records = [
        {"l": _fake_node(2, 4, 1.5, 3.5, "stud")},
        {"l": _fake_node(2, 6, 1.5, 5.5, "stud")},
        {"l": _fake_node(4, 4, 3.5, 3.5, "no2")},
    ]
    session.run.return_value = iter(records)

    specs = load_lumber_specs(session)
    assert set(specs.keys()) == {(2, 4), (2, 6), (4, 4)}
    assert specs[(4, 4)].grade == LumberGrade.NO2


def test_query_excludes_revoked_and_superseded_versions():
    """Loader must filter to ACTIVE current versions via Cypher (the WHERE)."""
    session = MagicMock()
    session.run.return_value = iter([])
    load_lumber_specs(session)

    cypher = session.run.call_args[0][0]
    assert '_status: "ACTIVE"' in cypher
    assert "NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec" in cypher
