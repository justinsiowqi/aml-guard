"""
Neo4j connection manager using the HTTPS Query API v2.

Uses only the Python standard library (urllib, base64, json) — no `neo4j`
driver dependency. See:
  https://neo4j.com/blog/developer/query-api-neo4j-aura-https/
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class Neo4jConnection:
    """
    HTTPS-based Neo4j connection.

    Posts Cypher to POST https://<host>/db/<database>/query/v2 with HTTP
    Basic auth. Query API v2 returns results as
        {"data": {"fields": [...], "values": [[...]]}}
    which this wrapper zips into list[dict] so callers keep the same
    interface as the bolt driver they replace.

    Usage (context manager):
        with Neo4jConnection() as conn:
            rows = conn.run_query("MATCH (n) RETURN count(n) AS total")
    """

    _DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._uri      = uri      or os.getenv("NEO4J_URI")
        self._username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self._password = password or os.getenv("NEO4J_PASSWORD")
        self._database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        self._timeout  = timeout

        if not all([self._uri, self._username, self._password]):
            raise ValueError(
                "Neo4j credentials are incomplete. "
                "Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD in your .env file."
            )

        # Strip any scheme so we always build https://<host> ourselves.
        host = self._uri
        for scheme in ("neo4j+s://", "neo4j+ssc://", "neo4j://", "https://", "http://"):
            if host.startswith(scheme):
                host = host[len(scheme):]
                break
        host = host.rstrip("/")

        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        self._url = f"https://{host}/db/{self._database}/query/v2"
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle — HTTP is stateless but we keep the interface for parity
    # ------------------------------------------------------------------

    def connect(self) -> "Neo4jConnection":
        """Verify connectivity with a ping and mark the connection ready."""
        self._connected = True
        try:
            self.run_query("RETURN 1 AS ping")
            logger.info("Connected to Neo4j at %s (database: %s)", self._url, self._database)
        except Exception:
            self._connected = False
            raise
        return self

    def close(self) -> None:
        """HTTP is stateless — just flip the flag for parity with the bolt driver."""
        self._connected = False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def run_query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict]:
        """
        Execute a Cypher query against the Query API v2.

        Returns result rows as list[dict] so it's drop-in compatible with
        callers that expected the bolt driver's record.data() shape.
        """
        if not self._connected:
            # Allow direct calls without explicit connect() — mirrors previous
            # behaviour where the bolt driver connected lazily on first query.
            self._connected = True

        payload: dict[str, Any] = {"statement": cypher}
        if params:
            payload["parameters"] = params

        req = urllib.request.Request(
            self._url,
            data=json.dumps(payload).encode(),
            headers=self._headers,
            method="POST",
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    body = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                err_body = _safe_read(e)
                if attempt == 0 and 500 <= e.code < 600:
                    logger.warning("Neo4j %d, retrying…", e.code)
                    continue
                raise RuntimeError(
                    f"Neo4j HTTP {e.code} at {self._url}: {err_body}"
                ) from e
            except urllib.error.URLError as e:
                if attempt == 0:
                    logger.warning("Neo4j connection error (%s), retrying…", e.reason)
                    continue
                raise RuntimeError(f"Neo4j unreachable at {self._url}: {e.reason}") from e

        if body.get("errors"):
            raise RuntimeError(f"Neo4j query error: {body['errors']}")

        data = body.get("data", {}) or {}
        fields = data.get("fields", []) or []
        values = data.get("values", []) or []
        return [dict(zip(fields, row)) for row in values]

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Neo4jConnection":
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def _safe_read(err: urllib.error.HTTPError) -> str:
    """Read the response body of an HTTPError, swallowing any secondary errors."""
    try:
        return err.read().decode(errors="replace")
    except Exception:
        return str(err)
