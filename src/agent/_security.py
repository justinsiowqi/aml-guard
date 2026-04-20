"""Prompt injection defence for agent tool result handling. Copied verbatim from loanguard-ai."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(your\s+)?(previous\s+)?instructions",
        r"forget\s+(your\s+)?instructions",
        r"new\s+system\s+prompt",
        r"you\s+are\s+now\s+a",
        r"act\s+as\s+a\s+different",
        r"override\s+your\s+(instructions|system|prompt)",
        r"do\s+not\s+follow\s+your",
        r"your\s+new\s+instructions\s+are",
    ]
]


def guard_tool_result(content: str, tool_name: str = "") -> str:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(content):
            logger.warning(
                "Possible prompt injection detected in tool result from '%s'. "
                "Pattern matched: '%s'. Content excerpt: %.200s",
                tool_name or "unknown",
                pattern.pattern,
                content,
            )
    label = f"TOOL DATA — {tool_name}" if tool_name else "TOOL DATA"
    return f"[{label}]\n{content}\n[END TOOL DATA]"
