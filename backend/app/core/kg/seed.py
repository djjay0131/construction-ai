"""Idempotent seed data for the construction KG.

Mirrors the original hardcoded ``LumberCalculator.LUMBER_SPECS`` set plus a
small starter set of framing roles and IRC code rules. Running ``seed_kg``
multiple times is safe: ``create_versioned_node`` no-ops when ``data_props``
are unchanged, and the relationship ``MERGE`` queries are idempotent by
construction.
"""

from __future__ import annotations

from typing import Any

from app.core.kg.provenance import create_versioned_node

LUMBER_SPECS: list[dict[str, Any]] = [
    {
        "identity": {"nominal_width": 2, "nominal_height": 4},
        "data": {
            "nominal": "2x4",
            "actual_width": 1.5,
            "actual_height": 3.5,
            "grade": "stud",
        },
    },
    {
        "identity": {"nominal_width": 2, "nominal_height": 6},
        "data": {
            "nominal": "2x6",
            "actual_width": 1.5,
            "actual_height": 5.5,
            "grade": "stud",
        },
    },
    {
        "identity": {"nominal_width": 2, "nominal_height": 8},
        "data": {
            "nominal": "2x8",
            "actual_width": 1.5,
            "actual_height": 7.25,
            "grade": "stud",
        },
    },
    {
        "identity": {"nominal_width": 2, "nominal_height": 10},
        "data": {
            "nominal": "2x10",
            "actual_width": 1.5,
            "actual_height": 9.25,
            "grade": "stud",
        },
    },
    {
        "identity": {"nominal_width": 2, "nominal_height": 12},
        "data": {
            "nominal": "2x12",
            "actual_width": 1.5,
            "actual_height": 11.25,
            "grade": "stud",
        },
    },
    {
        "identity": {"nominal_width": 4, "nominal_height": 4},
        "data": {
            "nominal": "4x4",
            "actual_width": 3.5,
            "actual_height": 3.5,
            "grade": "no2",
        },
    },
]

FRAMING_ROLES: list[str] = ["stud", "plate", "header"]

CODE_RULES: list[dict[str, Any]] = [
    {
        "identity": {"code": "IRC", "section": "R602.3"},
        "data": {
            "description": "Bearing wall stud spacing",
            "max_spacing_in": 16,
            "applies_to": "bearing_wall",
        },
    },
]


def seed_kg(session: Any) -> None:
    """Write seed nodes + relationships using the open neo4j ``session``.

    Idempotent: re-running with the same data is a no-op. Re-running with
    different ``data`` values creates a new version with a
    ``SUPERSEDED_BY`` chain (see ``provenance.create_versioned_node``).
    """
    with session.begin_transaction() as tx:
        for spec in LUMBER_SPECS:
            create_versioned_node(tx, "LumberSpec", spec["identity"], spec["data"])
        for role in FRAMING_ROLES:
            create_versioned_node(tx, "FramingRole", {"name": role}, {})
        for rule in CODE_RULES:
            create_versioned_node(tx, "CodeRule", rule["identity"], rule["data"])
        tx.commit()

    session.run(
        """
        MATCH (l:LumberSpec {_status: "ACTIVE"}),
              (r:FramingRole {name: "stud", _status: "ACTIVE"})
        WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
          AND NOT (r)-[:SUPERSEDED_BY]->(:FramingRole {_status: "ACTIVE"})
        MERGE (l)-[:USED_AS]->(r)
        """
    )
    session.run(
        """
        MATCH (r:FramingRole {name: "stud", _status: "ACTIVE"}),
              (c:CodeRule {code: "IRC", section: "R602.3", _status: "ACTIVE"})
        WHERE NOT (r)-[:SUPERSEDED_BY]->(:FramingRole {_status: "ACTIVE"})
          AND NOT (c)-[:SUPERSEDED_BY]->(:CodeRule {_status: "ACTIVE"})
        MERGE (r)-[:GOVERNED_BY]->(c)
        """
    )
