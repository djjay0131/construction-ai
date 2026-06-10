"""Unit tests for ``app.core.kg.client.Neo4jClient``.

Pure unit tests — no real Neo4j. The driver is replaced with a MagicMock so
we can verify the client's contract (construction, verify, session, close)
without spinning up a container.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.kg.client import Neo4jClient, Neo4jConnectionError


@pytest.fixture
def fake_driver():
    """Yield a (driver_mock, session_mock) pair patched into GraphDatabase."""
    driver = MagicMock()
    session_cm = MagicMock()  # context manager returned by driver.session()
    session = MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False
    driver.session.return_value = session_cm

    with patch("app.core.kg.client.GraphDatabase.driver", return_value=driver):
        yield driver, session


class TestConstruction:
    def test_empty_uri_raises_actionable_error(self):
        with pytest.raises(Neo4jConnectionError, match="non-empty URI"):
            Neo4jClient(uri="", user="neo4j", password="x")

    def test_constructs_driver_with_uri_and_credentials(self, fake_driver):
        driver, _ = fake_driver
        client = Neo4jClient("bolt://test:7687", "neo4j", "secret")
        assert client.uri == "bolt://test:7687"
        # GraphDatabase.driver was patched globally; verify call shape
        from app.core.kg.client import GraphDatabase
        GraphDatabase.driver.assert_called_once_with(
            "bolt://test:7687", auth=("neo4j", "secret")
        )


class TestVerify:
    def test_verify_runs_no_op_query_and_returns(self, fake_driver):
        _, session = fake_driver
        # session.run().single() should succeed
        run_result = MagicMock()
        run_result.single.return_value = {"ok": 1}
        session.run.return_value = run_result

        client = Neo4jClient("bolt://test:7687", "neo4j", "x")
        client.verify()  # should not raise

        session.run.assert_called_once_with("RETURN 1 AS ok")

    def test_verify_raises_with_uri_in_message_on_driver_failure(self, fake_driver):
        _, session = fake_driver
        session.run.side_effect = RuntimeError("unreachable host")

        client = Neo4jClient("bolt+s://aura.example", "neo4j", "x")
        with pytest.raises(Neo4jConnectionError, match=r"bolt\+s://aura\.example"):
            client.verify()


class TestSessionContextManager:
    def test_session_yields_driver_session(self, fake_driver):
        _, session = fake_driver
        client = Neo4jClient("bolt://test:7687", "neo4j", "x")
        with client.session() as s:
            assert s is session


class TestClose:
    def test_close_delegates_to_driver(self, fake_driver):
        driver, _ = fake_driver
        client = Neo4jClient("bolt://test:7687", "neo4j", "x")
        client.close()
        driver.close.assert_called_once()
