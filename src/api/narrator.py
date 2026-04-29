"""
Narrative LLM wrapper for the AML Guard /api/investigate response.

Runs as a post-processor over a deterministic CaseAssessment dict. When
AML_USE_AGENT_NARRATIVE=1 and credentials are present, calls H2OGPTe with
the aml_narrative prompts to generate human-readable headline / summary /
per-finding narratives / recommended_actions, then merges those into the
case payload. On any failure the original case is returned unchanged —
the narrator never raises.

The verdict and risk_score are NOT mutable here; this is purely a polish
layer over the rule-based trunk.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from src.core.client import create_client
from src.core.config import get_agent_config
from src.core.prompt_loader import load_message, load_prompt

logger = logging.getLogger(__name__)

_AGENT = "aml_narrative"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

# Lazy singleton — H2OGPTe requires a chat session anchored to a collection.
# We create one disposable collection per process for narrator use and reuse it.
_NARRATIVE_COLLECTION_LOCK = Lock()
_NARRATIVE_COLLECTION_ID: str | None = None


def enrich_with_narrative(case: dict[str, Any]) -> dict[str, Any]:
    """Wrap a deterministic CaseAssessment with LLM-generated narrative.

    Returns the input dict unchanged if the AML_USE_AGENT_NARRATIVE flag is
    off or any failure occurs in the LLM path.
    """
    if os.getenv("AML_USE_AGENT_NARRATIVE") != "1":
        return case
    started = time.perf_counter()
    try:
        narrative = _call_narrator(case)
    except Exception as e:
        logger.warning("Narrator failed (%s) — falling back to deterministic narrative.", e)
        return case
    elapsed_s = time.perf_counter() - started
    try:
        merged = _merge(case, narrative)
    except Exception as e:
        logger.warning("Narrator merge failed (%s) — returning deterministic case.", e)
        return case
    return _append_narrator_step(merged, elapsed_s)


def _append_narrator_step(case: dict[str, Any], elapsed_s: float) -> dict[str, Any]:
    """Add a narrative_synthesis step to investigation_steps so the UI stream
    has a fourth tile reflecting the LLM call we just made."""
    steps = list(case.get("investigation_steps") or [])
    findings_count = len(case.get("findings") or [])
    chunks_count = len(case.get("typology_chunks") or [])
    steps.append({
        "tool": "narrative_synthesis",
        "summary": (
            f"Drafted analyst narrative from {findings_count} finding"
            f"{'' if findings_count == 1 else 's'} and {chunks_count} chunk"
            f"{'' if chunks_count == 1 else 's'} ({elapsed_s:.1f}s)."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    })
    out = dict(case)
    out["investigation_steps"] = steps
    return out


def _call_narrator(case: dict[str, Any]) -> dict[str, Any]:
    client = create_client()
    cfg = get_agent_config(_AGENT)
    sys_prompt = load_prompt(_AGENT)

    payload = {
        "subject": case.get("subject", {}),
        "question": case.get("question", ""),
        "verdict": case.get("verdict", "CLEARED"),
        "risk_score": case.get("risk_score", 0.0),
        "findings": [
            {
                "pattern_name": f.get("pattern_name", ""),
                "severity": f.get("severity", ""),
                "description": f.get("description", ""),
            }
            for f in (case.get("findings") or [])
        ],
        "top_chunks": [
            {
                "section": c.get("section", ""),
                "text": c.get("text", ""),
            }
            for c in (case.get("typology_chunks") or [])[:3]
        ],
    }
    user_msg = load_message(_AGENT).format(payload=json.dumps(payload, indent=2))

    chat_id = client.create_chat_session(_get_narrative_collection(client))
    with client.connect(chat_id) as session:
        reply = session.query(
            message=user_msg,
            system_prompt=sys_prompt,
            llm=cfg["llm"],
            llm_args={"temperature": cfg.get("temperature", 0.2)},
            timeout=cfg.get("timeout_seconds", 30),
        )
    logger.info("aml_narrative reply received (in=%s out=%s).",
                getattr(reply, "input_tokens", "?"), getattr(reply, "output_tokens", "?"))
    return _parse_json(reply.content)


def _get_narrative_collection(client: Any) -> str:
    """Lazy-init a single shared collection for narrator chat sessions."""
    global _NARRATIVE_COLLECTION_ID
    with _NARRATIVE_COLLECTION_LOCK:
        if _NARRATIVE_COLLECTION_ID is None:
            _NARRATIVE_COLLECTION_ID = client.create_collection(
                name="AML Guard Narrator",
                description="Disposable collection for narrative LLM calls (no documents).",
            )
            logger.info("Narrator collection created: %s", _NARRATIVE_COLLECTION_ID)
        return _NARRATIVE_COLLECTION_ID


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = _FENCE_RE.sub("", text.strip())
    m = _JSON_BLOCK_RE.search(cleaned)
    if not m:
        raise ValueError(f"No JSON object in narrator reply: {text[:200]!r}")
    return json.loads(m.group(0))


def _merge(case: dict[str, Any], n: dict[str, Any]) -> dict[str, Any]:
    out = dict(case)
    if isinstance(n.get("headline"), str) and n["headline"].strip():
        out["headline"] = n["headline"].strip()
    if isinstance(n.get("summary"), str) and n["summary"].strip():
        out["summary"] = n["summary"].strip()
    if isinstance(n.get("recommended_actions"), list):
        actions = [a.strip() for a in n["recommended_actions"] if isinstance(a, str) and a.strip()]
        if actions:
            out["recommended_actions"] = actions
    fn = n.get("finding_narratives") or {}
    if isinstance(fn, dict) and case.get("findings"):
        out["findings"] = [
            {
                **f,
                "description": fn[f["pattern_name"]].strip()
                if isinstance(fn.get(f["pattern_name"]), str) and fn[f["pattern_name"]].strip()
                else f.get("description", ""),
            }
            for f in case["findings"]
        ]
    return out
