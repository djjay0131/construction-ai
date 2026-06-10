"""Universal versioning convention for all KG entities.

Every node type in the KG carries five reserved properties::

    _version: int       # monotonically increasing per logical entity
    _status:  str       # "ACTIVE" | "REVOKED"
    _created_at: str    # ISO 8601 UTC
    _created_by: str    # "seed", an agent id, etc.
    _reason: str        # human-readable rationale

Versioning is logical, not physical: each version is a separate node, and
``(:Old)-[:SUPERSEDED_BY]->(:New)`` chains them. The "current ACTIVE version"
is the one whose `_status = "ACTIVE"` and which has no outgoing
``SUPERSEDED_BY`` to another ACTIVE node. Rollback simply marks a version
``REVOKED``; the resolver then naturally returns the previous ACTIVE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 (kept tiny for testability)."""
    return datetime.now(timezone.utc).isoformat()


def create_versioned_node(
    tx: Any,
    label: str,
    identity_props: Mapping[str, Any],
    data_props: Mapping[str, Any],
    created_by: str = "seed",
    reason: str = "initial seed",
) -> None:
    """Write a new versioned node, or a new version if one already exists.

    Args:
        tx: An open neo4j transaction (or session — anything with ``.run``).
        label: Cypher label, e.g. ``"LumberSpec"``.
        identity_props: Properties that identify the logical entity
            (e.g. ``{"nominal_width": 2, "nominal_height": 4}``).
            These never change across versions.
        data_props: Properties that can change between versions
            (e.g. ``{"actual_width": 1.5, "grade": "STUD"}``).
        created_by: Audit field; defaults to ``"seed"``.
        reason: Audit field; defaults to ``"initial seed"``.

    Behavior:
        * No current ACTIVE version → create version 1.
        * Current ACTIVE version with identical ``data_props`` → no-op.
        * Current ACTIVE version with different ``data_props`` → create a new
          version one higher than the current and link the old to the new
          via ``SUPERSEDED_BY``.
    """
    now = _utcnow_iso()
    where = " AND ".join(f"n.{k} = ${k}" for k in identity_props)
    current_query = (
        f"MATCH (n:{label} {{_status: 'ACTIVE'}}) "
        f"WHERE {where} "
        f"AND NOT (n)-[:SUPERSEDED_BY]->(:{label} {{_status: 'ACTIVE'}}) "
        "RETURN n"
    )
    current = tx.run(current_query, **identity_props).single()

    all_props = {
        **identity_props,
        **data_props,
        "_status": "ACTIVE",
        "_created_at": now,
        "_created_by": created_by,
        "_reason": reason,
    }

    if current is None:
        all_props["_version"] = 1
        tx.run(f"CREATE (n:{label} $props)", props=all_props)
        return

    node = current["n"]
    if all(node.get(k) == v for k, v in data_props.items()):
        return  # no change → no-op (idempotent seed)

    all_props["_version"] = node["_version"] + 1
    tx.run(
        f"MATCH (old:{label}) WHERE elementId(old) = $old_id "
        f"CREATE (new:{label} $props) "
        "CREATE (old)-[:SUPERSEDED_BY]->(new)",
        old_id=node.element_id,
        props=all_props,
    )


def rollback_version(
    tx: Any,
    label: str,
    identity_props: Mapping[str, Any],
    version: int,
) -> None:
    """Mark a specific version REVOKED.

    The "current version" resolver naturally falls back to the next ACTIVE
    version once this one is REVOKED — no further wiring needed.

    Args:
        tx: An open neo4j transaction.
        label: Cypher label, e.g. ``"LumberSpec"``.
        identity_props: Properties identifying the logical entity.
        version: The ``_version`` integer to revoke.
    """
    where = " AND ".join(f"n.{k} = ${k}" for k in identity_props)
    tx.run(
        f"MATCH (n:{label} {{_version: $ver, _status: 'ACTIVE'}}) "
        f"WHERE {where} "
        "SET n._status = 'REVOKED'",
        ver=version,
        **identity_props,
    )
