"""Shared utilities for the AML Guard agent."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import openai

from src.agent.config import MAX_RETRY_SECONDS, TOOL_RESULT_CHAR_LIMIT

logger = logging.getLogger(__name__)

ENTITY_ID_RE = re.compile(r"(ENT|ACCT|TXN|ALERT|CASE)-\d+", re.IGNORECASE)


def clean_markdown(s: str) -> str:
    return s.strip().strip("*").strip()


def call_h2ogpte_with_retry(
    client: openai.OpenAI, *, label: str = "", **kwargs: Any
) -> openai.types.chat.ChatCompletion:
    for attempt in range(3):
        try:
            t0 = time.perf_counter()
            response = client.chat.completions.create(**kwargs)
            elapsed = time.perf_counter() - t0
            usage = response.usage
            tag = label or response.choices[0].finish_reason or ""
            logger.info(
                "%s %s %.2fs | in=%d out=%d",
                response.model, tag, elapsed,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
            )
            return response
        except openai.RateLimitError as e:
            if attempt < 2:
                retry_after = None
                try:
                    h = getattr(e, "response", None) and getattr(e.response, "headers", None)
                    if h:
                        retry_after = h.get("retry-after")
                        if retry_after is not None:
                            retry_after = min(int(float(retry_after)), MAX_RETRY_SECONDS)
                except (TypeError, ValueError):
                    pass
                wait = retry_after if retry_after is not None else min(30 * (2 ** attempt), MAX_RETRY_SECONDS)
                logger.warning("Rate limited — waiting %ds (attempt %d/3)", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise


def truncate_tool_result(content: str, limit: int = TOOL_RESULT_CHAR_LIMIT) -> str:
    if len(content) > limit:
        return content[:limit] + "… [truncated]"
    return content


def extract_text(response: openai.types.chat.ChatCompletion) -> str:
    return response.choices[0].message.content or ""


def trim_message_history(
    messages: list[dict], max_pairs: int, anchor_count: int = 1
) -> list[dict]:
    anchor = messages[:anchor_count]
    tail   = messages[anchor_count:]
    max_tail_msgs = max_pairs * 2
    if len(tail) <= max_tail_msgs:
        return anchor + tail
    trimmed = tail[-(max_tail_msgs):]
    if trimmed[0].get("role") == "user":
        trimmed = trimmed[1:]
    return anchor + trimmed
