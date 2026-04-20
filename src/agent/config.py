"""Shared configuration constants for the AML Guard agent."""

from __future__ import annotations

import os

import anthropic

MODEL_MAIN = "claude-sonnet-4-6"
MODEL_FAST = "claude-haiku-4-5-20251001"
MODEL      = MODEL_MAIN

MAX_TOKENS           = 8096
SYNTHESIS_MAX_TOKENS = 2048
TEMPERATURE          = 0

CACHE_CONTROL_EPHEMERAL: dict = {"type": "ephemeral"}

TOOL_RESULT_CHAR_LIMIT  = 3000
PRE_RUN_RESULT_CHAR_LIMIT = 4096

MAX_RETRY_SECONDS = 120

EMBEDDING_MODEL = "text-embedding-3-small"

# Single agent — max agentic loop iterations and context window pairs.
AML_MAX_ITERATIONS   = 14
AML_MAX_HISTORY_PAIRS = 6


def make_anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        default_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
