"""
In-memory job registry for the async deep-analysis flow.

The deep-analysis agent loop is a 5–10 minute blocking call into H2OGPTe. We
can't hold a synchronous HTTP request open that long, so /api/investigate/deep
spawns a background thread and returns a job_id immediately. The frontend then
polls /api/investigate/deep/status/{job_id} to see real progress (derived from
H2OGPTe chat-session messages) and pick up the final result.

The registry is a plain dict guarded by a Lock. It does not survive a uvicorn
restart — acceptable for the demo. The in-flight agent thread continues even
if the client cancels (the H2OGPTe SDK has no abort API); a cancel only stops
the UI from watching, and the result is discarded on completion.

# How the agent transcript is mined

H2OGPTe packs the entire agent loop's intermediate output into the reply
message's `type_list` as a series of `ChatMessageMeta` entries. Critically,
the public `list_chat_messages` API JSON-stringifies these entries (h2ogpte.py
:3082), which destroys their structure — we use `list_chat_messages_full`
instead so we can read each entry's `message_type` and `content`.

Per-turn the agent emits a cluster like:
    code_dict       — the Python code block it ran this turn
    agent_files     — Python files written this turn
    agent_files_pdf — PDF artifacts produced
    usage           — token counts
    turn_budget     — budget tracker
    turn_message    — human-readable narration of what just happened
    turn_title      — short headline for the turn

We group entries into "turns" by treating `turn_title` as the turn boundary
(it's emitted at the end of each turn). Everything since the previous
turn_title gets folded into the current turn's card.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal

logger = logging.getLogger(__name__)

JobStatus = Literal["running", "done", "error", "cancelled"]

# Phase strings live here so the frontend stays dumb — it just renders whatever
# phase_label the backend hands back. Adding a new tool means editing one place.
DEEP_PHASES: list[str] = [
    "Resolving entity from question…",         # 0
    "Traversing 2-hop entity subgraph…",        # 1
    "Detecting graph anomaly patterns…",        # 2
    "Retrieving MAS Notice 626 typology chunks…",  # 3
    "Synthesising verdict…",                    # 4
]

# Substring → phase index. Matched case-insensitively against new agent
# activity (turn messages + code blocks). Phase index is monotonic.
# Markers are intentionally loose — the agent narrates by step number and
# capability ("Step 1 — traverse the subgraph") rather than the underscore
# tool name, so exact tool names rarely appear in turn_message content.
_PHASE_MARKERS: list[tuple[str, int]] = [
    ("traverse_entity_network", 1),
    ("step 1", 1),
    ("step1_traverse", 1),
    ("detect_graph_anomalies", 2),
    ("step 2", 2),
    ("step2_detect", 2),
    ("retrieve_typology_chunks", 3),
    ("step 3", 3),
    ("step3_typology", 3),
]

# message_type values we care about for the transcript. Everything else
# (turn_budget, usage, prompt_raw, py_client_code, agent_chat_history*,
# agent_venv_requirements, agent_meta, agent_chat_history_md, hyde1, etc.)
# is diagnostic noise and ignored for UI purposes.
_TYPE_TURN_TITLE = "turn_title"
_TYPE_TURN_MESSAGE = "turn_message"
_TYPE_CODE_DICT = "code_dict"
_TYPE_AGENT_FILES = "agent_files"
_TYPE_AGENT_FILES_PDF = "agent_files_pdf"
_TYPE_AGENT_ANALYSIS = "agent_analysis"
_TYPE_USAGE_STATS = "usage_stats"

_TURN_MAX_MESSAGE = 2000
_TURN_MAX_CODE = 1500

# Prefix for chat-message-derived event ids — lets the frontend distinguish
# live agent events from deterministic-trunk steps.
_AGENT_EVENT_PREFIX = "h2ogpte-"

# Raw `turn_title` values H2OGPTe assigns to housekeeping turns. We drop these
# unless the paired `turn_message` contains a semantic step keyword (handled
# in _synthesize_title).
_NOISE_TITLE_PATTERNS = [
    re.compile(r"^executing\s+python\s+code\s+block$", re.I),
    re.compile(r"^agent\s+working$", re.I),
    re.compile(r"^agent\s+setting\s+up\s+environment$", re.I),
    re.compile(r"^agent\s+(initiating|starting)", re.I),
    re.compile(r"^checking\s+(available\s+)?mcp", re.I),
    re.compile(r"^checking\s+mcp\s+tool", re.I),
]

# Patterns scanned against `turn_message` to synthesise a meaningful title
# when the raw turn_title is generic noise. Order matters — first match wins.
# Each entry is (regex, displayed_title). A None label means "drop the card".
# Compiled case-insensitive.
#
# NOTE: these are only applied when the raw turn_title is noise. When H2OGPTe
# emits a descriptive raw title (e.g. "Follow-up AML Tool Call — Node 11011597
# (MINERVA TRUST…)" or "AML Risk Assessment: NIELSEN ENTERPRISES — HIGH_RISK"),
# we trust it directly — see _synthesize_title.
_MESSAGE_TITLE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpre-?emit\s+self[- ]?check\b", re.I), "Pre-emit self-check"),
    (re.compile(r"\bi'?ll\s+investigate\b", re.I), "Planning the investigation"),
    (re.compile(r"\bstep\s*1\s+complete\b", re.I), "Step 1 complete · subgraph traversal"),
    (re.compile(r"\bstep\s*2\s+complete\b", re.I), "Step 2 complete · anomaly detection"),
    (re.compile(r"\bstep\s*3\s+complete\b", re.I), "Step 3 complete · typology retrieval"),
    (re.compile(r"\ball\s+three\s+steps\s+(are\s+)?complete\b", re.I), "All three steps complete · synthesising verdict"),
    (re.compile(r"\bnow\s+(running\s+)?step\s*1\b", re.I), "Starting Step 1 · subgraph traversal"),
    (re.compile(r"\bnow\s+(running\s+)?step\s*2\b", re.I), "Starting Step 2 · anomaly detection"),
    (re.compile(r"\bnow\s+(running\s+)?step\s*3\b", re.I), "Starting Step 3 · typology retrieval"),
    (re.compile(r"\b(diagrams?\s+rendered|subgraph\s+rendered|render(ing)?\s+the\s+risk\s+(composition\s+)?pie)\b", re.I), None),  # drop diagram-render turns
    (re.compile(r"\b(timed?\s+out|timeout)\b", re.I), "Tool timed out"),
]

# Regex to extract "node <id> (<NAME>)" from a turn message — used to enrich
# generic follow-up tool call titles with entity context.
_FOLLOWUP_NODE_RE = re.compile(
    r"(?:node[_\s]+|node_id[_\s]+|scoped\s+to[_\s]+|intermediary[_\s]+)(\d{5,})"
    r"(?:[^(]*\(([^)]{3,80})\))?",
    re.I,
)
# Regex to extract a VERDICT line from the message (for AML assessment cards).
_VERDICT_IN_MSG_RE = re.compile(
    r"\bVERDICT\s*:\s*(HIGH_RISK|MEDIUM_RISK|LOW_RISK|CLEARED)\b", re.I
)
# Broad pattern to pick the subject entity name from the message (ALL-CAPS
# company names). Matches the longest run of upper-cased words containing
# "LIMITED", "LTD", "TRUST", "HOLDINGS", "GROUP", "CORP", "ENTERPRISES".
_ENTITY_NAME_RE = re.compile(
    r"\b([A-Z][A-Z\s&,\.]{3,60}"
    r"(?:LIMITED|LTD|TRUST|HOLDINGS|GROUP|CORP|ENTERPRISES|SERVICES))\b"
)


def _maybe_enrich_title(title: str, message: str) -> str:
    """Append entity / verdict context to known H2OGPTe base titles.

    H2OGPTe sometimes emits a short base title (e.g. "Follow-up AML Tool
    Call") where its own UI adds entity IDs and names extracted from the
    tool-call arguments.  We replicate that enrichment by mining the paired
    turn_message.
    """
    if not message:
        return title
    tl = title.lower()

    # Enrich follow-up tool call cards with the intermediary node they target.
    if "follow-up" in tl and ("tool call" in tl or "tool" in tl):
        m = _FOLLOWUP_NODE_RE.search(message)
        if m:
            node_id = m.group(1)
            entity  = (m.group(2) or "").strip()
            suffix  = f"Node {node_id}" + (f" ({entity})" if entity else "")
            # Avoid appending if the node_id is already in the title.
            if node_id not in title:
                return f"{title} — {suffix}"

    # Enrich AML-assessment / risk-assessment cards with verdict + entity.
    if "assessment" in tl or "risk" in tl or "verdict" in tl:
        vm = _VERDICT_IN_MSG_RE.search(message)
        em = _ENTITY_NAME_RE.search(message)
        if vm and em and vm.group(1) not in title and em.group(1) not in title:
            return f"{title} — {em.group(1).strip()} · {vm.group(1).upper()}"
        elif vm and vm.group(1) not in title:
            return f"{title} — {vm.group(1).upper()}"

    return title


def _is_noise_title(title: str) -> bool:
    t = title.strip()
    return any(p.match(t) for p in _NOISE_TITLE_PATTERNS)


# H2OGPTe emits its own boot logs as turn_message content, e.g.
# `[Thursday, May 21, 2026 - 04:19:48.1 AM PDT] Agent begins setting up ...`
# These leak into the agent's narrative slot if not stripped. Recognised by
# the leading bracketed timestamp + "Agent begins …".
_BOOT_LOG_RE = re.compile(r"^\[.*?\]\s+agent\s+begins\b", re.I)

# Eager step titles H2OGPTe emits BEFORE the agent has narrated anything
# meaningful for that step. We drop them when no narration is paired so the
# transcript stays in chronological order — the agent will emit a better
# "Step N complete · …" card from its own narrative shortly after.
_EAGER_STEP_TITLE_RE = re.compile(r"^step\s*\d+\s+[—\-]", re.I)


def _strip_boot_message(message: str) -> str:
    """Return message content with boot/setup logs stripped."""
    s = (message or "").strip()
    if not s:
        return ""
    if _BOOT_LOG_RE.match(s):
        return ""
    return s


def _synthesize_title(raw_title: str, message: str) -> str | None:
    """Pick the title to display, or return None to drop the card.

    Strategy (updated): trust H2OGPTe's raw turn_title first — it often
    carries rich entity / verdict context (e.g. "Follow-up AML Tool Call —
    Node 11011597 (MINERVA TRUST…)") that message-rule synthesis would
    flatten to something generic.

    Fallback to message-rule synthesis only when the raw title is housekeeping
    noise.  Explicit "drop" signals (label=None in _MESSAGE_TITLE_RULES) are
    checked against the message regardless of which path we're on — a diagram-
    render turn is always dropped.
    """
    msg = _strip_boot_message(message)

    # Always honour explicit drop signals (label is None) so diagram-render
    # turns and other unwanted cards never surface.
    for pattern, label in _MESSAGE_TITLE_RULES:
        if label is None and msg and pattern.search(msg):
            return None

    # --- Primary path: use the raw H2OGPTe title when it's meaningful ---
    if not _is_noise_title(raw_title):
        title = raw_title.strip()
        # Drop eager "Step N — …" headers that arrive before the agent has
        # written any narration — the richer "Step N complete · …" card from a
        # later turn is preferred over a bare step-number header.
        if not msg and _EAGER_STEP_TITLE_RE.match(title):
            return None
        if title:
            return _maybe_enrich_title(title, msg)

    # --- Fallback: synthesise from the message when raw title is noise ---
    if msg:
        for pattern, label in _MESSAGE_TITLE_RULES:
            if pattern.search(msg):
                return label  # may be None — "drop" signal

    return None  # noise title with no useful message → drop


def _event_id(msg_id: str, title: str, message: str) -> str:
    """Stable content-derived id so React keys don't flicker when the backend
    fully re-extracts agent_events on every poll. Same (title, message-prefix)
    always hashes to the same id within a chat session."""
    h = hashlib.md5(f"{title}|{(message or '')[:200]}".encode("utf-8")).hexdigest()[:12]
    return f"{_AGENT_EVENT_PREFIX}{msg_id}-{h}"


@dataclass
class DeepJob:
    job_id: str
    question: str
    started_at: float
    status: JobStatus = "running"
    chat_session_id: str | None = None
    phase_idx: int = 0
    phase_label: str = field(default_factory=lambda: DEEP_PHASES[0])
    last_message_count: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    llm_used: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    # Live agent transcript — one card per meaningful agent turn. The list is
    # fully recomputed on every refresh_phase() call from the latest
    # list_chat_messages_full snapshot. Stable content-hashed ids ([_event_id])
    # keep React keys stable so the UI doesn't flicker. Frontend renders this
    # in the dedicated AgentTranscript component (NOT Investigation Stream).
    # Each entry: {id, kind, turn_idx, title, message, code, files, timestamp}.
    agent_events: list[dict[str, Any]] = field(default_factory=list)


_REGISTRY: dict[str, DeepJob] = {}
_LOCK = Lock()
_PRUNE_AFTER_SECONDS = 3600  # 1 hour


def create_job(question: str) -> DeepJob:
    """Register a new job and return it. Opportunistically prunes old jobs."""
    job = DeepJob(
        job_id=uuid.uuid4().hex,
        question=question,
        started_at=time.monotonic(),
    )
    with _LOCK:
        _REGISTRY[job.job_id] = job
        _prune_locked()
    logger.info("Created deep job %s for question: %s", job.job_id, question[:80])
    return job


def get_job(job_id: str) -> DeepJob | None:
    with _LOCK:
        return _REGISTRY.get(job_id)


def update_job(job_id: str, **fields: Any) -> None:
    """Patch a job's fields in-place. Silently no-ops if the job is gone."""
    with _LOCK:
        job = _REGISTRY.get(job_id)
        if job is None:
            return
        for k, v in fields.items():
            if hasattr(job, k):
                setattr(job, k, v)


def mark_cancelled(job_id: str) -> bool:
    """Mark a job cancelled. Returns True if found, False otherwise.

    The backend thread keeps running — H2OGPTe has no abort API. The result
    will be discarded on completion (the worker checks status before merging).
    """
    with _LOCK:
        job = _REGISTRY.get(job_id)
        if job is None:
            return False
        if job.status == "running":
            job.status = "cancelled"
        return True


def _prune_locked() -> None:
    now = time.monotonic()
    stale = [
        jid for jid, j in _REGISTRY.items()
        if now - j.started_at > _PRUNE_AFTER_SECONDS
    ]
    for jid in stale:
        del _REGISTRY[jid]
    if stale:
        logger.info("Pruned %d stale deep jobs", len(stale))


def refresh_phase(job: DeepJob, client: Any) -> None:
    """Re-extract the agent transcript and phase index from H2OGPTe.

    Uses `list_chat_messages_full` (rather than `list_chat_messages`, which
    JSON-stringifies type_list — see h2ogpte.py:3082). We *fully recompute*
    `agent_events` on every call rather than tracking incremental offsets:

    - H2OGPTe returns each message's `type_list` in REVERSE-chronological
      order (latest entries at low indices). Tracking a forward offset there
      is brittle — when new entries arrive at the front, every old entry
      shifts. Easier to just re-extract.

    - We use stable content-hashed event ids so React keys are stable across
      recomputes — the UI doesn't flicker even though the list is replaced.

    - Cost: each poll ≈ 1 REST call + scanning ~50–150 small entries. Trivial
      next to the agent loop itself.
    """
    if job.chat_session_id is None or job.status != "running":
        return
    try:
        messages = client.list_chat_messages_full(
            job.chat_session_id,
            offset=0,
            limit=50,
        )
    except Exception as e:
        logger.debug("refresh_phase: list_chat_messages_full failed: %s", e)
        return

    if not messages:
        return

    highest_phase = job.phase_idx
    fresh_events: list[dict[str, Any]] = []

    for msg in messages:
        msg_id = str(getattr(msg, "id", "") or "")
        type_list = list(getattr(msg, "type_list", None) or [])
        if not type_list:
            continue
        # H2OGPTe returns type_list in REVERSE-chronological order. Reverse
        # for chronological processing so turn boundaries land in run order
        # and turn_idx grows naturally.
        chronological = list(reversed(type_list))
        msg_events, msg_phase = _process_entries(msg_id, chronological)
        if msg_phase > highest_phase:
            highest_phase = msg_phase
        fresh_events.extend(msg_events)

    # If any agent_analysis or final_summary landed, the run is wrapping up.
    has_analysis = any(ev.get("kind") == "agent_analysis" for ev in fresh_events)
    if has_analysis or any(ev.get("kind") == "final_summary" for ev in fresh_events):
        if highest_phase < 4:
            highest_phase = 4

    # Drop the synthesised "Planning the investigation" turn if we already
    # surface the agent's plan as the dedicated agent_analysis card — same
    # content, no need to render it twice. (Chronological ordering means we
    # only learn this after the full pass.)
    if has_analysis:
        fresh_events = [
            ev for ev in fresh_events
            if not (ev.get("kind") == "turn" and ev.get("title") == "Planning the investigation")
        ]

    # Renumber visible turn cards 0..N in chronological order. Plan stays at
    # -1, final_summary stays at 999.
    turn_counter = 0
    for ev in fresh_events:
        if ev.get("kind") == "turn":
            ev["turn_idx"] = turn_counter
            turn_counter += 1

    update_job(
        job.job_id,
        agent_events=fresh_events,
        phase_idx=highest_phase,
        phase_label=DEEP_PHASES[highest_phase],
        last_message_count=len(messages),
    )


def _process_entries(
    msg_id: str,
    entries: list[Any],
) -> tuple[list[dict[str, Any]], int]:
    """Walk type_list entries (chronological order) and emit one card per
    meaningful turn. Synthesises titles from the paired turn_message when
    the raw turn_title is generic, drops housekeeping noise, and dedupes
    consecutive identical synthesised titles.

    Returns: (events, highest_phase).
    """
    events: list[dict[str, Any]] = []
    highest_phase = 0
    pending: dict[str, Any] = {}
    last_emitted_title: str | None = None
    saw_analysis = False
    saw_usage_stats = False

    def _emit_turn(raw_title: str) -> None:
        nonlocal last_emitted_title
        message = _strip_boot_message(pending.get("message", ""))
        synthesized = _synthesize_title(raw_title, message)
        if synthesized is None:
            return  # housekeeping noise — drop
        if synthesized == last_emitted_title:
            return  # consecutive duplicate
        last_emitted_title = synthesized
        events.append({
            "id": _event_id(msg_id, synthesized, message),
            "kind": "turn",
            "turn_idx": 0,  # renumbered after full pass
            "title": synthesized,
            "message": _truncate(message, _TURN_MAX_MESSAGE),
            "code": _truncate(pending.get("code", ""), _TURN_MAX_CODE) if pending.get("code") else None,
            "files": list(pending.get("files", [])),
            "timestamp": _iso_now(),
        })

    for entry in entries:
        mt = (getattr(entry, "message_type", "") or "").lower()
        raw = getattr(entry, "content", "") or ""

        for needle, idx in _PHASE_MARKERS:
            if needle in raw.lower() and idx > highest_phase:
                highest_phase = idx

        if mt == _TYPE_AGENT_ANALYSIS and not saw_analysis:
            text = _parse_json_or_text(raw)
            events.append({
                "id": _event_id(msg_id, "agent_reasoning", text),
                "kind": "agent_analysis",
                "turn_idx": -1,
                "title": "Agent reasoning",
                "message": _truncate(text, _TURN_MAX_MESSAGE * 2),
                "code": None,
                "files": [],
                "timestamp": _iso_now(),
            })
            saw_analysis = True
            continue

        if mt == _TYPE_USAGE_STATS and not saw_usage_stats:
            stats = _try_load_json(raw)
            summary_text = (
                _format_usage_stats(stats) if isinstance(stats, dict)
                else _truncate(raw, _TURN_MAX_MESSAGE)
            )
            events.append({
                "id": _event_id(msg_id, "run_summary", summary_text),
                "kind": "final_summary",
                "turn_idx": 999,
                "title": "Run summary",
                "message": summary_text,
                "code": None,
                "files": [],
                "timestamp": _iso_now(),
            })
            saw_usage_stats = True
            continue

        if mt == _TYPE_TURN_MESSAGE:
            pending["message"] = _parse_json_or_text(raw)
        elif mt == _TYPE_CODE_DICT:
            pending["code"] = _extract_code(raw)
        elif mt in (_TYPE_AGENT_FILES, _TYPE_AGENT_FILES_PDF):
            pending.setdefault("files", []).extend(_extract_file_names(raw))
        elif mt == _TYPE_TURN_TITLE:
            # Boundary — emit (possibly synthesised) card, then reset.
            _emit_turn(_parse_json_or_text(raw))
            pending = {}

    return events, highest_phase


def _parse_json_or_text(raw: str) -> str:
    """type_list content is often a JSON-quoted string; unwrap if so."""
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith('"') and s.endswith('"'):
        try:
            return json.loads(s)
        except Exception:
            pass
    return s


def _try_load_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_code(raw: str) -> str:
    """code_dict entries are JSON like {"lang": "python", "code": "..."}."""
    obj = _try_load_json(raw)
    if isinstance(obj, dict):
        return obj.get("code") or ""
    return raw


def _extract_file_names(raw: str) -> list[str]:
    """agent_files / agent_files_pdf entries are JSON like
    [{"<file_id>": "filename.ext"}, ...]. Return the filenames only."""
    obj = _try_load_json(raw)
    out: list[str] = []
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                for v in item.values():
                    if isinstance(v, str):
                        out.append(v)
    return out


def _format_usage_stats(stats: dict[str, Any]) -> str:
    """One-line summary of the final usage_stats block (response_time, cost,
    tokens, llm). Keeps known fields, ignores the rest."""
    parts: list[str] = []
    if "response_time" in stats:
        parts.append(str(stats["response_time"]).strip())
    if "llm" in stats:
        parts.append(f"model={stats['llm']}")
    if "input_tokens" in stats:
        parts.append(f"in_tok={stats['input_tokens']}")
    if "output_tokens" in stats:
        parts.append(f"out_tok={stats['output_tokens']}")
    if "cost" in stats:
        parts.append(f"cost={stats['cost']}")
    return " · ".join(parts) if parts else ""


def _truncate(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
