"""Load the current ACTIVE specs from Neo4j into an in-memory dict.

Called once at FastAPI startup. The returned dict is then handed to
``LumberCalculator`` so per-request takeoff lookups stay O(1) without ever
touching Neo4j again.
"""

from __future__ import annotations

from typing import Any

from app.schemas.material import LumberGrade, LumberSpecification


def load_lumber_specs(
    session: Any,
) -> dict[tuple[int, int], LumberSpecification]:
    """Return ``{(nominal_width, nominal_height): LumberSpecification}``.

    Resolves the current ACTIVE version per logical entity by excluding
    nodes that have a ``SUPERSEDED_BY`` edge to another ACTIVE node — that's
    the universal versioning convention from ``provenance.py``.
    """
    results = session.run(
        """
        MATCH (l:LumberSpec {_status: "ACTIVE"})
        WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
        RETURN l
        """
    )
    specs: dict[tuple[int, int], LumberSpecification] = {}
    for record in results:
        node = record["l"]
        key = (node["nominal_width"], node["nominal_height"])
        specs[key] = LumberSpecification(
            nominal_width=node["nominal_width"],
            nominal_height=node["nominal_height"],
            actual_width=node["actual_width"],
            actual_height=node["actual_height"],
            grade=LumberGrade(node["grade"]),
        )
    return specs
