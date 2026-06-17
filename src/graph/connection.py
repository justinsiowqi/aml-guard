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
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Dedicated logger for the Cypher audit trail. Emits a one-line summary to the
# console (visible in the uvicorn terminal) and appends a structured JSONL
# record to a file for reproducibility / customer-facing "these are real
# Neo4j queries" evidence. Toggle with AML_CYPHER_AUDIT (default on); change
# the output path with AML_CYPHER_AUDIT_FILE (default logs/cypher_audit.jsonl).
_CYPHER_LOGGER = logging.getLogger("aml.cypher")

# Trivial connectivity probes we don't want cluttering the audit trail.
_AUDIT_SKIP = {"RETURN 1 AS ping", "RETURN 1 AS ok"}


def _inline_cypher(cypher: str, params: dict[str, Any] | None) -> str:
    """Return a copy-pasteable Cypher string with $params substituted by their
    literal values. For display / reproducibility only — the app always executes
    the parameterised form. json.dumps yields valid Cypher literals for strings
    (double-quoted), numbers, booleans, null, and lists.
    """
    if not params:
        return " ".join(cypher.split())
    out = " ".join(cypher.split())
    # Replace longer keys first so $entity_id isn't clipped by $entity.
    for key in sorted(params, key=len, reverse=True):
        literal = json.dumps(params[key], ensure_ascii=False, default=str)
        out = re.sub(rf"\${re.escape(key)}(?![A-Za-z0-9_])", lambda _m: literal, out)
    return out


def _audit_query(
    cypher: str, params: dict[str, Any] | None, rows: int, elapsed_ms: float
) -> None:
    """Append one query to the audit trail. Never raises — auditing must not
    affect query results."""
    if os.getenv("AML_CYPHER_AUDIT", "1") != "1":
        return
    if " ".join(cypher.split()) in _AUDIT_SKIP:
        return
    try:
        reproducible = _inline_cypher(cypher, params)
        record = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "elapsed_ms": round(elapsed_ms, 1),
            "rows": rows,
            "cypher": " ".join(cypher.split()),
            "params": params or {},
            "reproducible": reproducible,
        }
        path = os.getenv("AML_CYPHER_AUDIT_FILE") or os.path.join("logs", "cypher_audit.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        _CYPHER_LOGGER.info("[cypher] rows=%s %.0fms :: %s", rows, elapsed_ms, reproducible)
    except Exception as e:
        logger.debug("Cypher audit failed (non-fatal): %s", e)


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

        started = time.perf_counter()
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
        rows = [dict(zip(fields, row)) for row in values]
        _audit_query(cypher, params, len(rows), (time.perf_counter() - started) * 1000)
        return rows

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
