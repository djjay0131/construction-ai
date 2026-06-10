"""Unit tests for ``app.core.kg.provenance``.

Pure unit tests using a MagicMock transaction. We assert on the Cypher
queries the function sends (not on Neo4j behavior — that's covered in
the integration tests).
"""

from unittest.mock import MagicMock

from app.core.kg.provenance import create_versioned_node, rollback_version


def _fake_tx_no_current():
    """tx.run(...).single() returns None — i.e., no existing version."""
    tx = MagicMock()
    tx.run.return_value.single.return_value = None
    return tx


def _fake_tx_with_current(version, data_props):
    """tx.run(...).single() returns a fake node record."""
    tx = MagicMock()
    node = MagicMock()
    node.__getitem__.side_effect = lambda k: data_props[k] if k in data_props else {"_version": version}[k]
    node.get = lambda k, default=None: data_props.get(k, default)
    node.element_id = "id-1234"
    # Make node["_version"] return the version
    items = {"_version": version, **data_props}
    node.__getitem__.side_effect = items.__getitem__
    record = {"n": node}
    tx.run.return_value.single.return_value = record
    return tx


class TestCreateVersionedNodeFirstTime:
    def test_first_write_creates_version_1(self):
        tx = _fake_tx_no_current()
        create_versioned_node(
            tx,
            "LumberSpec",
            {"nominal_width": 2, "nominal_height": 4},
            {"actual_width": 1.5, "grade": "stud"},
        )
        # Expected: one MATCH + one CREATE
        assert tx.run.call_count == 2
        create_call = tx.run.call_args_list[1]
        cypher = create_call[0][0]
        assert "CREATE (n:LumberSpec $props)" in cypher
        props = create_call[1]["props"]
        assert props["_version"] == 1
        assert props["_status"] == "ACTIVE"
        assert props["_created_by"] == "seed"
        assert props["_reason"] == "initial seed"
        assert props["actual_width"] == 1.5

    def test_passes_through_created_by_and_reason(self):
        tx = _fake_tx_no_current()
        create_versioned_node(
            tx,
            "LumberSpec",
            {"nominal_width": 2, "nominal_height": 6},
            {"actual_width": 1.5},
            created_by="api",
            reason="manual update by Jane",
        )
        props = tx.run.call_args_list[1][1]["props"]
        assert props["_created_by"] == "api"
        assert props["_reason"] == "manual update by Jane"


class TestCreateVersionedNodeIdempotent:
    def test_same_data_is_noop_when_current_matches(self):
        tx = _fake_tx_with_current(
            version=1, data_props={"actual_width": 1.5, "grade": "stud"}
        )
        create_versioned_node(
            tx,
            "LumberSpec",
            {"nominal_width": 2, "nominal_height": 4},
            {"actual_width": 1.5, "grade": "stud"},
        )
        # Only the MATCH query ran; no CREATE
        assert tx.run.call_count == 1


class TestCreateVersionedNodeUpdates:
    def test_changed_data_creates_new_version_with_supersedes_chain(self):
        tx = _fake_tx_with_current(
            version=1, data_props={"actual_width": 1.5, "grade": "stud"}
        )
        create_versioned_node(
            tx,
            "LumberSpec",
            {"nominal_width": 2, "nominal_height": 4},
            {"actual_width": 1.625, "grade": "stud"},  # actual_width changed
        )
        assert tx.run.call_count == 2
        update_call = tx.run.call_args_list[1]
        cypher = update_call[0][0]
        assert "MATCH (old:LumberSpec)" in cypher
        assert "CREATE (new:LumberSpec $props)" in cypher
        assert "CREATE (old)-[:SUPERSEDED_BY]->(new)" in cypher
        props = update_call[1]["props"]
        assert props["_version"] == 2
        assert update_call[1]["old_id"] == "id-1234"


class TestRollbackVersion:
    def test_marks_version_revoked(self):
        tx = MagicMock()
        rollback_version(
            tx,
            "LumberSpec",
            {"nominal_width": 2, "nominal_height": 4},
            version=2,
        )
        tx.run.assert_called_once()
        cypher, params = tx.run.call_args[0][0], tx.run.call_args[1]
        assert "_version: $ver" in cypher
        assert "_status: 'ACTIVE'" in cypher
        assert "SET n._status = 'REVOKED'" in cypher
        assert params["ver"] == 2
        assert params["nominal_width"] == 2
        assert params["nominal_height"] == 4
