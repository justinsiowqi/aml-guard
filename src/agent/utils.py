"""Shared utilities for the AML Guard agent."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from h2ogpte.types import Answer, SessionError

from src.agent.config import MAX_RETRY_SECONDS, TOOL_RESULT_CHAR_LIMIT

logger = logging.getLogger(__name__)

ENTITY_ID_RE = re.compile(r"(ENT|ACCT|TXN|ALERT|CASE)-\d+", re.IGNORECASE)


def clean_markdown(s: str) -> str:
    return s.strip().strip("*").strip()


def query_with_retry(session: Any, *, label: str = "", **kwargs: Any) -> Answer:
    """
    Call session.query() with up to 3 retries on SessionError.

    H2OGPTe manages conversation history server-side, so callers only pass
    the current message and llm_args — no message list to maintain.

    Logs one INFO line per successful call:
        <label|finish> <elapsed>s | in=N out=N
    """
    for attempt in range(3):
        try:
            t0 = time.perf_counter()
            reply: Answer = session.query(**kwargs)
            elapsed = time.perf_counter() - t0
            tag = label or "ok"
            logger.info(
                "%s %.2fs | in=%d out=%d",
                tag, elapsed,
                reply.input_tokens or 0,
                reply.output_tokens or 0,
            )
            return reply
        except TimeoutError:
            if attempt < 2:
                wait = min(30 * (2 ** attempt), MAX_RETRY_SECONDS)
                logger.warning("Timeout — retrying in %ds (attempt %d/3)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise
        except SessionError as e:
            if attempt < 2:
                logger.warning("SessionError: %s — retrying in 30s (attempt %d/3)", e, attempt + 1)
                time.sleep(30)
            else:
                raise


def extract_text(reply: Answer) -> str:
    """Return the text content of an H2OGPTe Answer."""
    return reply.content or ""


def truncate_tool_result(content: str, limit: int = TOOL_RESULT_CHAR_LIMIT) -> str:
    """
    Truncate a tool result string to `limit` characters before passing it
    back to the model. Keeps context size bounded across a long investigation
    loop where accumulated tool results would otherwise grow unbounded.
    """
    if len(content) > limit:
        return content[:limit] + "… [truncated]"
    return content
