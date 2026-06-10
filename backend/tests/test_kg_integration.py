"""Integration tests for the KG package against a real Neo4j container.

Uses ``testcontainers[neo4j]`` to spin up an ephemeral Neo4j 5.x community
container per test session. These tests are marked ``integration`` so they
can be skipped via ``-m 'not integration'`` if Docker isn't available
(though Docker is the project's standing dev-environment requirement).
"""

from __future__ import annotations

import logging
import os

import pytest
from neo4j import GraphDatabase

from app.core.kg.client import Neo4jClient
from app.core.kg.loader import load_lumber_specs
from app.core.kg.provenance import create_versioned_node, rollback_version
from app.core.kg.seed import LUMBER_SPECS, seed_kg

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)

# Skip the whole module if testcontainers can't reach Docker.
try:
    from testcontainers.neo4j import Neo4jContainer
except Exception:  # pragma: no cover - import-time failure surfaces as collection skip
    Neo4jContainer = None  # type: ignore


if Neo4jContainer is None:
    pytest.skip(
        "testcontainers[neo4j] not importable; skip integration tests",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def neo4j_container():
    """Spin up a single Neo4j container for the whole test session."""
    if not os.environ.get("DOCKER_HOST") and not os.path.exists("/var/run/docker.sock"):
        # On macOS docker-desktop uses a different socket; testcontainers handles this.
        pass
    try:
        container = Neo4jContainer("neo4j:5-community")
        container.start()
    except Exception as exc:
        pytest.skip(f"Neo4j testcontainer failed to start: {exc}")
        return
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture
def session(neo4j_container):
    """Fresh per-test session against the shared container, with cleanup."""
    uri = neo4j_container.get_connection_url()
    auth = (neo4j_container.username, neo4j_container.password)
    driver = GraphDatabase.driver(uri, auth=auth)
    s = driver.session()
    try:
        # Clean slate per test
        s.run("MATCH (n) DETACH DELETE n")
        yield s
    finally:
        s.close()
        driver.close()


@pytest.fixture
def client(neo4j_container):
    """A real Neo4jClient backed by the container."""
    uri = neo4j_container.get_connection_url()
    c = Neo4jClient(uri, neo4j_container.username, neo4j_container.password)
    try:
        yield c
    finally:
        c.close()


class TestClientVerify:
    """AC-1: client.verify() against a real instance."""

    def test_verify_succeeds_against_running_instance(self, client):
        client.verify()  # should not raise


class TestSeedAndLoad:
    """AC-2 + AC-3 + AC-10: seed populates with provenance, idempotent."""

    def test_seed_creates_six_lumber_specs(self, session):
        seed_kg(session)
        result = session.run(
            """
            MATCH (l:LumberSpec {_status: "ACTIVE"})
            WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
            RETURN count(l) AS n
            """
        ).single()
        assert result["n"] == len(LUMBER_SPECS) == 6

    def test_each_seeded_spec_has_provenance_properties(self, session):
        seed_kg(session)
        result = session.run(
            """
            MATCH (l:LumberSpec {_status: "ACTIVE"})
            WHERE NOT (l)-[:SUPERSEDED_BY]->(:LumberSpec {_status: "ACTIVE"})
            RETURN l._version AS v, l._status AS s, l._created_at AS ts,
                   l._created_by AS cb, l._reason AS reason
            """
        )
        for row in result:
            assert row["v"] == 1
            assert row["s"] == "ACTIVE"
            assert row["ts"]  # ISO 8601 string, non-empty
            assert row["cb"] == "seed"
            assert row["reason"] == "initial seed"

    def test_stud_role_governed_by_irc_r602_3(self, session):
        seed_kg(session)
        result = session.run(
            """
            MATCH (r:FramingRole {name: "stud", _status: "ACTIVE"})
                  -[:GOVERNED_BY]->
                  (c:CodeRule {code: "IRC", section: "R602.3", _status: "ACTIVE"})
            RETURN r, c
            """
        ).single()
        assert result is not None
        assert result["c"]["max_spacing_in"] == 16

    def test_seed_is_idempotent(self, session):
        seed_kg(session)
        first = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        seed_kg(session)
        second = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        assert first == second  # no new nodes


class TestLoadLumberSpecs:
    """AC-2 round-trip: seed then load returns the 6 expected dict entries."""

    def test_loader_returns_six_specs_keyed_by_dimensions(self, session):
        seed_kg(session)
        specs = load_lumber_specs(session)
        assert len(specs) == 6
        assert (2, 4) in specs
        assert specs[(2, 4)].actual_width == 1.5
        assert specs[(2, 4)].actual_height == 3.5


class TestVersionHistory:
    """AC-8: re-seeding with changed data creates a new version."""

    def test_changed_data_creates_v2_with_supersedes_chain(self, session):
        seed_kg(session)
        # Manually overwrite (2,4) data to a different actual_width via API
        with session.begin_transaction() as tx:
            create_versioned_node(
                tx,
                "LumberSpec",
                {"nominal_width": 2, "nominal_height": 4},
                {"nominal": "2x4", "actual_width": 1.5625, "actual_height": 3.5, "grade": "stud"},
                created_by="test",
                reason="testing v2",
            )
            tx.commit()

        # v1 should still exist with original data
        v1 = session.run(
            "MATCH (l:LumberSpec {nominal_width: 2, nominal_height: 4, _version: 1}) RETURN l"
        ).single()
        assert v1 is not None
        assert v1["l"]["actual_width"] == 1.5

        # v2 should exist and supersede v1
        chain = session.run(
            """
            MATCH (v1:LumberSpec {_version: 1, nominal_width: 2, nominal_height: 4})
                  -[:SUPERSEDED_BY]->
                  (v2:LumberSpec {_version: 2})
            RETURN v2
            """
        ).single()
        assert chain is not None
        assert chain["v2"]["actual_width"] == 1.5625

        # Loader returns v2 values
        specs = load_lumber_specs(session)
        assert specs[(2, 4)].actual_width == 1.5625


class TestRollback:
    """AC-9: rollback marks v2 REVOKED; resolver falls back to v1."""

    def test_rollback_restores_previous_active_version(self, session):
        seed_kg(session)
        # Create v2
        with session.begin_transaction() as tx:
            create_versioned_node(
                tx,
                "LumberSpec",
                {"nominal_width": 2, "nominal_height": 4},
                {"nominal": "2x4", "actual_width": 1.5625, "actual_height": 3.5, "grade": "stud"},
            )
            tx.commit()

        # Rollback v2
        with session.begin_transaction() as tx:
            rollback_version(
                tx,
                "LumberSpec",
                {"nominal_width": 2, "nominal_height": 4},
                version=2,
            )
            tx.commit()

        # Resolver should now return v1
        specs = load_lumber_specs(session)
        assert specs[(2, 4)].actual_width == 1.5
