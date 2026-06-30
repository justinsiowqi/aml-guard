"""
Merge logic for /api/investigate/deep — combines a deterministic CaseAssessment
with an H2OGPTe agent's AMLRiskResponse.

Ownership boundaries:
  - Agent owns:        verdict (with band-distance guardrail), risk_score,
                       headline, summary, recommended_actions, triggered_typologies_agent.
  - Deterministic:     subgraph, findings[], typology_chunks, evidence_ids,
                       investigation_steps, tx_velocity, risk_decomposition,
                       connection_focus, subject, case_id.

Band-distance guardrail: if the agent's verdict differs from the deterministic
verdict by more than one band on VERDICT_PRIORITY, keep the deterministic
verdict and log a WARNING. Prevents a parser glitch from silently downgrading
HIGH_RISK -> CLEARED.
"""

from __future__ import annotations

import logging
from typing import Any

from src.mcp.schema import AMLRiskResponse, VERDICT_PRIORITY

logger = logging.getLogger(__name__)

_VALID_VERDICTS = set(VERDICT_PRIORITY.keys())


def _verdict_band_distance(a: str, b: str) -> int:
    pa = VERDICT_PRIORITY.get(a, -1)
    pb = VERDICT_PRIORITY.get(b, -1)
    if pa < 0 or pb < 0:
        return 99
    return abs(pa - pb)


def _extract_summary_from_answer(answer: str) -> str:
    """Pull the SUMMARY: ... block out of the agent's raw markdown reply.

    Matches the multi-line summary up to the next FIELD: header. Returns
    the stripped text or empty string if not found.
    """
    import re
    m = re.search(
        r"^\s*SUMMARY\s*:\s*(.+?)(?=^\s*[A-Z][A-Z_]{2,}\s*:|\Z)",
        answer,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    if not m:
        return ""
    return m.group(1).strip()


def merge_agent_into_case(case: dict[str, Any], resp: AMLRiskResponse) -> dict[str, Any]:
    """Layer the agent's narrative-and-verdict outputs onto a deterministic case.

    Returns a new dict (does not mutate input).
    """
    out = dict(case)

    deterministic_verdict = case.get("verdict", "CLEARED")
    if resp.verdict in _VALID_VERDICTS:
        distance = _verdict_band_distance(resp.verdict, deterministic_verdict)
        if distance <= 1:
            out["verdict"] = resp.verdict
            out["risk_score"] = float(resp.risk_score)
        else:
            logger.warning(
                "Agent verdict %s diverges %d bands from deterministic %s; keeping deterministic.",
                resp.verdict, distance, deterministic_verdict,
            )

    summary_text = _extract_summary_from_answer(resp.answer)
    if summary_text:
        out["summary"] = summary_text
        # Use first sentence of summary as headline, capped at 140 chars.
        first_sentence = summary_text.split(". ")[0].strip().rstrip(".")
        out["headline"] = (first_sentence + ".")[:140]

    if resp.recommended_actions:
        out["recommended_actions"] = list(resp.recommended_actions)

    if resp.triggered_typologies:
        out["triggered_typologies_agent"] = list(resp.triggered_typologies)

    steps = list(out.get("investigation_steps") or [])
    findings_count = len(out.get("findings") or [])
    steps.append({
        "tool": "h2ogpte_session_query",
        "summary": (
            f"Agent reviewed {findings_count} finding"
            f"{'' if findings_count == 1 else 's'}; verdict={resp.verdict}, "
            f"score={resp.risk_score:.2f}."
        ),
        "timestamp": case.get("created_at", ""),
    })
    out["investigation_steps"] = steps

    return out
