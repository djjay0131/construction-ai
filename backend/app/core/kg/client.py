"""Neo4j connection client.

Thin wrapper around the official neo4j Python driver. Supports any URI scheme
the driver supports (``bolt+s://`` for AuraDB Free in prod, ``bolt://`` for
local-dev or ephemeral testcontainer in CI). The wrapper exists so callers
don't reach into driver internals and so startup verification has one place
to live.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from neo4j import GraphDatabase, Session

logger = logging.getLogger(__name__)


class Neo4jConnectionError(RuntimeError):
    """Raised when the Neo4j instance is unreachable or rejects credentials.

    The error message always includes the URI we attempted to reach, so
    misconfigured `NEO4J_URI` values surface a clear, actionable error.
    """


class Neo4jClient:
    """Manages a single Neo4j driver and provides session context managers.

    The driver is created at construction; ``verify`` runs a no-op query to
    confirm the connection is alive. Call ``close`` at process shutdown.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        if not uri:
            raise Neo4jConnectionError(
                "Neo4jClient requires a non-empty URI; check NEO4J_URI in your .env"
            )
        self._uri = uri
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    @property
    def uri(self) -> str:
        return self._uri

    def verify(self) -> None:
        """Run a trivial query to confirm the connection is reachable.

        Raises Neo4jConnectionError on any driver-level failure, with the URI
        included in the message.
        """
        try:
            with self._driver.session() as session:
                session.run("RETURN 1 AS ok").single()
        except Exception as exc:
            raise Neo4jConnectionError(
                f"Neo4j verification failed for URI {self._uri!r}: {exc}"
            ) from exc

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Yield a session; the driver handles per-session cleanup."""
        with self._driver.session() as session:
            yield session

    def close(self) -> None:
        """Close the underlying driver. Safe to call multiple times."""
        self._driver.close()
