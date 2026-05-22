# AML Guard — H2OGPTe Agent Integration

Living doc covering the two H2OGPTe integration paths (Phase 1 narrator + Phase 2 deep-analysis agent), how to run them, what's still mock vs. real on the frontend, and what to build next.

> **Doc location rationale**: kept in the repo's `docs/` folder (rather than Obsidian) so it's versioned with the code and `git blame` reveals when claims went stale. If a section's last modification predates the file it describes, treat it as suspect.

---

## 1. Current state

### Phase 1 — Narrator (default investigation flow)

**Triggered by**: every call to `POST /api/investigate` (i.e. the regular investigate flow on the homepage).

**What it does**: runs the deterministic trunk first (graph traversal → anomaly detection → typology vector search → score / verdict). Then a **single non-agentic** H2OGPTe call rewrites the headline, summary, per-finding descriptions, and recommended actions. Verdict and risk_score are NOT mutable here — the narrator only re-words.

**Files**
- [src/api/narrator.py](../src/api/narrator.py) — wrapper, JSON parsing, fence-stripping, fallback handling
- [src/prompts/aml_narrative_sys.md](../src/prompts/aml_narrative_sys.md) + `aml_narrative_message.md` — strict-JSON prompt
- [src/api/main.py](../src/api/main.py) `investigate()` — wires `enrich_with_narrative()` post-processor
- [config/agents.yaml](../config/agents.yaml) — `aml_narrative` entry (`llm: auto`, temp 0.2, 30s timeout)

**Gating flag**: `AML_USE_AGENT_NARRATIVE=1` in `.env`. With the flag off, response is byte-identical to the deterministic trunk.

**Cost / latency**: ~3–8s, sub-cent. Single LLM call.

### Phase 2 — Deep Analysis (real H2OGPTe agent loop, async job pattern)

**Triggered by**: clicking the "Run Deep Analysis" button in `VerdictBanner` after a normal investigation has settled.

**Request flow (3 endpoints)**:
1. `POST /api/investigate/deep` — runs the deterministic trunk synchronously (we need its subgraph + findings + evidence_ids), then spawns a daemon thread running the H2OGPTe agent loop and returns immediately with `{ job_id, case }`. The frontend renders the deterministic baseline straight away.
2. `GET /api/investigate/deep/status/{job_id}` — polled by the frontend every 2.5s. Returns `{ status, phase_idx, phase_label, elapsed_seconds, input_tokens, output_tokens, result, error }`. On each call, the backend pulls fresh messages from H2OGPTe (`list_chat_messages`, offset-tracked) and infers the current phase by substring-matching tool names against message content.
3. `POST /api/investigate/deep/cancel/{job_id}` — marks the job cancelled. Frontend stops polling. **The backend thread keeps running and still bills** — H2OGPTe SDK has no abort API. The result is dropped on completion. The UI button is labelled "Stop Watching" for honesty.

**What the agent does (E′ — Pre-loaded Context Agent)**: invokes `AMLAgent.start_async(..., trunk_evidence=case)` which makes one `session.query(...)` call with `use_agent=True`. The deterministic trunk's results (subject, subgraph, findings, typology_chunks) are formatted as JSON and **injected into the user message** under a `## Pre-computed evidence` section. The agent reads this evidence directly instead of re-calling the three baseline MCP tools — that work is already done by the trunk.

The agent's job is reduced to: synthesise the verdict from the pre-loaded evidence + emit follow-up MCP tool calls only when a specific gap exists (unscoped Intermediary, missing rubric pattern, underspecified citations). For clean runs the agent makes **0 follow-up calls** and emits a single output block in ~30–60s (was 5–10min before E′). For ambiguous cases it issues 1–2 follow-up tool calls, adding ~30–60s per call.

H2OGPTe still spawns the Coder Agent with access to:
- `aml_guard_mcp.zip` (Neo4j-backed: `traverse_entity_network_tool`, `detect_graph_anomalies_tool`, `retrieve_typology_chunks_tool`) — kept available for follow-up
- `claude_tool_runner.py` (built-in MCP dispatcher)
- `mermaid_renderer.py` is still uploaded but no longer used — the output format dropped the mermaid diagram mandate. Frontend renders subgraph + risk composition from deterministic data.

The agent's response is parsed by `_parse_response()` (regex extraction of `VERDICT / RISK_SCORE / SUMMARY / TRIGGERED_TYPOLOGIES / CITED_CHUNKS / RECOMMENDED_ACTIONS`) and merged into the deterministic case via `merge_agent_into_case()`. After the agent returns, `_log_followup_tool_calls()` scans the captured `agent_events` for references to the three MCP tool names and logs `details={'traverse_entity_network': N, 'detect_graph_anomalies': N, 'retrieve_typology_chunks': N}` so you can confirm the agentic + Neo4j integration is still live (counts will be 0+ for clean runs, 1+ for follow-ups). The three MCP tool implementations in [src/mcp/tools_impl.py](../src/mcp/tools_impl.py) also each log a `[tool-call]` line at INFO level on every invocation — useful for the deterministic trunk path; the agent's calls run in H2OGPTe's sandbox so those logs land on the H2OGPTe server, not in our uvicorn output.

**Phase mapping** (single source of truth: `DEEP_PHASES` in [src/api/jobs.py](../src/api/jobs.py)):
| Idx | Label | Trigger |
|---|---|---|
| 0 | Resolving entity from question… | initial / collection setup |
| 1 | Traversing 2-hop entity subgraph… | `step 1`, `traverse_entity_network`, or `step1_traverse` substring |
| 2 | Detecting graph anomaly patterns… | `step 2`, `detect_graph_anomalies`, or `step2_detect` substring |
| 3 | Retrieving MAS Notice 626 typology chunks… | `step 3`, `retrieve_typology_chunks`, or `step3_typology` substring |
| 4 | Synthesising verdict… | `agent_analysis` or `usage_stats` entry seen |

Phase index is monotonic — once we see phase 3 we never report a lower phase. Markers are intentionally loose because H2OGPTe's Coder Agent narrates by step number / capability ("Step 1 — traverse the subgraph") rather than the underscore tool name.

**Agent transcript extraction.** The Coder Agent packs its entire loop into the reply message's `type_list` as `ChatMessageMeta` entries (turn_title, turn_message, code_dict, agent_files, agent_analysis, usage_stats, plus diagnostic noise). Two gotchas determined the current design:

1. The public `list_chat_messages` API **JSON-stringifies** these entries ([h2ogpte.py:3082](../.venv/lib/python3.12/site-packages/h2ogpte/h2ogpte.py#L3082)), destroying their structure. `refresh_phase` uses `list_chat_messages_full` instead, which preserves them as `ChatMessageMeta` with the `message_type` field intact.
2. H2OGPTe returns each message's `type_list` in **reverse-chronological** order (index 0 = latest, index N-1 = earliest), and **prepends** new entries as the agent works. Tracking a forward offset across polls is brittle — every new entry shifts the older ones. So `refresh_phase` fully re-extracts `agent_events` on every poll from the latest snapshot, using **stable content-hashed event ids** (`hashlib.md5(title|msg-prefix)`) so React keys stay stable and the UI doesn't flicker.

The extractor walks `type_list` in chronological order (reversed) and groups entries by `turn_title` boundary. For each boundary, it synthesises a displayed title from the paired `turn_message` content rather than using the raw `turn_title` directly — H2OGPTe often labels real step turns as the generic "Executing python code block", with the meaningful step status ("Step 2 complete. The intermediary_shell_network pattern fired…") only in the message. Synthesis rules drop noise (`Agent Working`, `Agent Setting up Environment`, `Checking MCP Tools`, diagram rendering), promote semantic step status ("Step N complete · …", "Starting Step N · …", "Planning the investigation", "All three steps complete · synthesising verdict"), and de-dupe consecutive identical titles. The agent's overall plan from the dedicated `agent_analysis` entry is pinned at the top as a "Plan" card; the final `usage_stats` block becomes the bottom "Run summary" card with cost + timing.

**Files**
- [src/api/jobs.py](../src/api/jobs.py) — `DeepJob` dataclass, in-memory registry, `refresh_phase()` polls H2OGPTe
- [src/agent/aml_agent.py](../src/agent/aml_agent.py) — `AMLAgent.setup()`, `.start_async()` (with `on_started` / `on_reply` callbacks), `.run()` (sync wrapper), `_parse_response()`
- [src/api/merge.py](../src/api/merge.py) — agent-vs-deterministic merge with band-distance guardrail
- [src/api/main.py](../src/api/main.py) — `_get_agent()` singleton, `/api/investigate/deep` (job submit), `/status/{job_id}`, `/cancel/{job_id}`, `_run_deep_job()` worker
- [src/core/setup.py](../src/core/setup.py) — `register_mcp_tool()` (idempotent), `upload_and_ingest_mcp()`, `setup_agent_keys()`
- [src/mcp/aml_guard_mcp.zip](../src/mcp/aml_guard_mcp.zip) — bundled MCP tool functions (rebuild with `python src/mcp/bundle.py` after editing `src/mcp/tools_impl.py`)
- [src/prompts/aml_sys.md](../src/prompts/aml_sys.md) — E′ system prompt: "evidence is pre-loaded, synthesise + optional follow-up tools" workflow, scoring rubric, output format (no mermaid)
- [src/prompts/aml_message.md](../src/prompts/aml_message.md) — user-message template with `## Pre-computed evidence` placeholders rendered by `_evidence_placeholders()` in [src/agent/aml_agent.py](../src/agent/aml_agent.py)
- [config/agents.yaml](../config/agents.yaml) — `aml` entry (`llm: claude-sonnet-4-6`, agent_max_turns 20, agent_total_timeout 900s)
- Frontend: [web/lib/api.ts](../web/lib/api.ts) (`startDeepAnalysis`, `getDeepStatus`, `cancelDeepAnalysis`), [web/app/investigate/page.tsx](../web/app/investigate/page.tsx) (poll loop), [web/components/VerdictBanner.tsx](../web/components/VerdictBanner.tsx) (real phase strip, "Stop Watching" button), [web/components/AgentTranscript.tsx](../web/components/AgentTranscript.tsx) (dedicated panel rendering the live turn-by-turn transcript). The Investigation Stream component is **not** used for agent events — it remains dedicated to the deterministic trunk + narrator steps.

**Merge ownership**
| Field | Source |
|---|---|
| verdict, risk_score | agent (with band-distance ≤1 guardrail; otherwise deterministic wins) |
| headline, summary, recommended_actions | agent |
| triggered_typologies_agent (informational) | agent |
| subject, case_id, subgraph, findings, typology_chunks, investigation_steps | deterministic |
| tx_velocity, risk_decomposition, connection_focus | deterministic |

**Cost / latency** (under E′ + Sonnet 4.6 pin): **~30–90 seconds, ~$0.05–$0.20 per click** for clean runs (zero follow-up tool calls), extending to **~2–4 minutes, ~$0.50–$1** when the agent makes 1–2 follow-up calls. Was 5–10 min / $5–$15 before E′ because the agent re-ran the three baseline MCP tools every time. Hard caps: `agent_max_turns: 20`, `agent_total_timeout: 900s`.

**Frontend progress**: the 5-phase strip in `VerdictBanner` is driven by real H2OGPTe chat-session messages (`getDeepStatus` polls every 2.5s; the backend pulls fresh messages via `client.list_chat_messages_full()` and infers phase by substring-matching). The same poll extracts **`agent_events`** (one card per agent turn) and the frontend renders them in a **dedicated `AgentTranscript` panel** below the verdict row — separate from the Investigation Stream (which is kept untouched for the deterministic + narrator path). Each card shows the turn title, the agent's narration of what just happened, expandable code + artifact list. The button to halt is labelled **"Stop Watching"** (not "Cancel") because the H2OGPTe agent run continues server-side and still bills — only the UI stops waiting.

**Startup pre-warm**: the FastAPI `lifespan` handler in [src/api/main.py](../src/api/main.py) spawns a daemon thread on boot that calls `_get_agent()`, so the first user click doesn't pay the 30–90s collection-create + MCP-upload cost. Logged as `H2OGPTe agent ready in {dt}s` once complete. Set `AML_DISABLE_PREWARM=1` to skip (useful in tests). Pre-warm failures are non-fatal — first real click retries with the same try/except.

---

## 2. How to run / replicate

### Prerequisites (one-time)

```bash
# Python deps
pip install -r requirements.txt

# .env file in project root with:
H2OGPTE_API_KEY=...
H2OGPTE_ADDRESS=https://h2ogpte.internal.dedicated.h2o.ai
NEO4J_URI=...
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
AML_USE_AGENT_NARRATIVE=1   # enable Phase 1
```

### Standard run

```bash
# Terminal 1 — backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — frontend
cd web
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

Browser → `http://localhost:3000`.

### Replicating the deep-analysis output

1. Type any question (e.g. "Investigate Nielsen Enterprises" or "Who really owns Nielsen Enterprises Limited?") and submit.
2. Wait for the verdict to settle (~10s with Phase 1 narrator on).
3. Click **"Run Deep Analysis"** in the verdict banner.
4. Phase strip animates while the H2OGPTe agent runs (5–10 min).
5. When it lands, the verdict banner re-renders with the agent's headline / summary / verdict / score / recommended_actions.

### When to rebuild the MCP bundle

After editing any of `src/mcp/tools_impl.py`, `src/mcp/queries.py`, `src/mcp/schema.py`, `src/graph/connection.py`, `src/mcp/server.py`:

```bash
python src/mcp/bundle.py
# → writes src/mcp/aml_guard_mcp.zip
```

Then restart uvicorn so the singleton agent re-uploads the fresh zip on the next deep-analysis call.

---

## 3. Mock-vs-real audit (what's actually wired to backend data)

### Real (backend / graph / agent driven)

| UI element | Source |
|---|---|
| Subject card (name, jurisdiction, profile) | Neo4j Company node properties |
| Verdict + risk score | Deterministic `_score()` (Phase 1), or agent (Phase 2) |
| Headline | `_headline()` (off), narrator (Phase 1), or agent (Phase 2) |
| Summary text under headline | Phase 1 narrator or Phase 2 agent (only present when one of them ran) |
| Recommended actions list | Phase 1 narrator or Phase 2 agent |
| Findings list (with descriptions) | Real anomaly registry hits + per-finding narrator rewrite when on |
| Typology chunks (citations) | Real vector search over MAS-626 (`retrieve_typology_chunks`) |
| Subgraph visualisation | Real Neo4j 2-hop traversal |
| Investigation Stream tool steps | Real tool calls from the deterministic trunk + narrator append |
| Connection Focus card | Computed from the real subgraph |
| Risk Decomposition bars | Computed from real findings + typology chunks |

### Mock / scripted (NOT backend driven)

| UI element | Reason | File |
|---|---|---|
| `tx_velocity` sparkline (12-month volume) | No `Transaction` nodes in Layer 1 — value is `_synth_tx_velocity(case_id)`, an md5-derived deterministic fingerprint | [src/api/assembler.py:273](../src/api/assembler.py#L273) |
| Verification Protocol checklist item 1 ("Sanctions & watchlist screening") | No sanctions feed wired — static rationale "Screening stub — no sanctions feed wired in this build" | [VerdictBanner.tsx:72](../web/components/VerdictBanner.tsx#L72) |
| Verification Protocol checklist item 2 ("Source of funds documented") | No transaction data — static rationale "Source-of-funds stub — Transaction nodes pending Layer 1 expansion" | [VerdictBanner.tsx:86](../web/components/VerdictBanner.tsx#L86) |
| Verification Protocol items 3–4 ("Typology evidence reviewed", "Case narrative drafted") | Rationale text IS dynamic (computed from real findings/chunks) — but the **cycling "thinking" sub-messages** during verification are scripted | [VerdictBanner.tsx:209](../web/components/VerdictBanner.tsx#L209) (real) / [VerdictBanner.tsx:62](../web/components/VerdictBanner.tsx#L62) (mock thoughts) |
| "Approve & Escalate" downstream pipeline (Approval Agent → Filing Agent → MAS Submission) | Pure client-side animation. No agents are actually invoked, no SAR is filed. Tokens like `{caseId}` get substituted from real data but the work is fake | [VerdictBanner.tsx:130](../web/components/VerdictBanner.tsx#L130) |
| Investigation Stream rolling thoughts during streaming | Cycling messages on the active step are scripted (`NARRATIVE_THOUGHTS`, `GENERIC_THOUGHTS`); real tool steps appear once the API returns | [InvestigationStream.tsx:26](../web/components/InvestigationStream.tsx#L26) |
| Mock-mode entire response (when `NEXT_PUBLIC_API_BASE` is unset) | All questions resolve to `mocks/nielsen-enterprises.json` regardless of input — useful for offline dev, dishonest as a demo | [web/lib/mock-adapter.ts](../web/lib/mock-adapter.ts) |
| `mockStartDeep` / `mockGetDeepStatus` (Run Deep Analysis in mock mode) | ~12.5s simulated lifecycle that walks through the 5 phases and then returns the Nielsen mock with a hand-written summary/actions | [web/lib/mock-adapter.ts](../web/lib/mock-adapter.ts) |

### Phase 2 fields the agent already emits but the UI doesn't surface

These are present on the merged `CaseAssessment` after deep analysis but no component renders them yet:

| Field | What it is | Suggested surface |
|---|---|---|
| `triggered_typologies_agent: string[]` | Pattern names the agent flagged in its narrative | A small pills row under the verdict, distinct from the registry-driven `findings[]` |
| Agent's `SUBGRAPH_DIAGRAM` mermaid block (currently buried inside `summary`) | The agent renders its own graph diagram in mermaid | Extract during parse; render alongside or instead of `EntitySubgraph` when in deep mode |
| Agent's `RISK_COMPOSITION` mermaid pie (currently buried in `summary`) | Per-rubric-input weights | Replace or augment the `RiskDecomposition` bar chart |
| Agent's individual `RECOMMENDED_ACTIONS` items | Currently rendered as a flat bulleted list | Group/expand with rationale, route to handoff queue |
| Per-finding `description` rewritten by narrator | Already wired into `findings[].description` ✓ | (already done) |

---

## 4. Future work

Grouped roughly by effort.

### Quick wins (½–1 day each)

- **Surface `triggered_typologies_agent`** as a pills row below the verdict so the deep-analysis UX has something visibly distinct from the deterministic flow.
- **Extract the agent's mermaid diagrams** during `_parse_response()` into separate fields (`subgraph_mermaid`, `risk_composition_mermaid`) instead of leaving them embedded in the summary. Then render with a mermaid viewer (e.g. `mermaid` npm package).
- **Final-run cost meter** — once a job completes, surface `reply.usage_stats` (cost, response_time, llm) in a small "Run cost: $X.XX · Y.Ys · {llm}" row on the verdict panel. Live tokens are already shown during the run; this would add the post-hoc dollar figure.
- **Resume-in-flight job via URL** — persist `job_id` in the URL query string so a page reload mid-run can reattach to the existing job and keep polling instead of orphaning it.

### Medium (2–4 days each)

- **Replace `tx_velocity` synth with real transaction data** — requires Layer 1 schema expansion to add `Transaction` nodes. Once data exists, drop `_synth_tx_velocity()`.
- **Wire item 1 of the verification protocol to a real sanctions screen** — even a free OFAC SDN list lookup would be more honest than the current static stub.
- **Per-finding agent narratives** — the agent currently emits one `SUMMARY` block; could instead prompt it for one short paragraph per finding, then merge those into `findings[i].description` for richer per-finding text in deep mode.

### Larger (a week+)

- **SSE / WebSocket progress** — the polling pattern works but adds ~24 HTTP calls per minute of wait. Switching the status endpoint to SSE (push the same payload only when the phase actually changes) would cut traffic and reduce latency between phase transitions.
- **Persistent job store** — current in-memory job registry doesn't survive `uvicorn --reload`. SQLite or Redis would let jobs outlive backend restarts (important when a fresh code edit lands mid-investigation).
- **Replace `mock-adapter.ts` with a per-question presets system** — currently every question routes to Nielsen. Add 2–3 presets keyed by entity name so demo mode tells different stories.
- **Caching layer** for deep analysis — same question + same Neo4j state → cached result. The job registry already keys by job_id; an extension keyed by `(question, neo4j_revision)` would short-circuit duplicate $12 runs.
- **Approve & Escalate → real handoff** — wire the pipeline animation to actual downstream services (or at least persist the case to a real queue).

---

## 5. Known gotchas / tech debt

- [src/agent/utils.py:11](../src/agent/utils.py#L11) imports `SessionError` from `h2ogpte`, which the installed SDK no longer exports. Anything importing this module will fail at import time. Currently nothing on the hot path imports it but a future contributor might trip over it.
- The MCP zip (`src/mcp/aml_guard_mcp.zip`) is checked into the repo and **must be rebuilt manually** after edits to source under `src/mcp/`. There's no CI / pre-commit hook to enforce this. If the agent starts producing weird tool errors, suspect a stale zip first.
- `cost_controls.max_cost: 0.05` in `llm_args` is **ignored** by H2OGPTe under `llm: "auto"` — actual cost has hit $12+. Pin a specific model to gate cost, or remove the cost_controls block to stop pretending it works.
- `agent_total_timeout: 900` (15 min) is generous for the demo. Real Step 1+2+3 finishes in 5–8 min in practice. The SDK timeout auto-derives to 960s.
- `SERVER_FILE` in `src/core/setup.py` resolves relative to the file's own directory, NOT the project root — so the path is robust to running uvicorn from anywhere.
- **Deep-analysis job registry is in-memory only** ([src/api/jobs.py](../src/api/jobs.py)). A `uvicorn --reload` (triggered by any code edit during a running deep analysis) drops the registry — the agent thread keeps running, finishes, and bills, but the result vanishes from the UI. Acceptable for the demo; switch to SQLite/Redis for any production use.
- **"Stop Watching" is honest, not forceful** — the H2OGPTe SDK has no abort API. Cancelling a job stops the frontend polling and discards the result on completion, but the agent loop runs to completion server-side and still bills. UI tooltip wording is set up to communicate this; do not silently change it to "Cancel".

---

*Last updated: 2026-05-21. Shipped E′ — Pre-loaded Context Agent: the deterministic trunk's case (subject, subgraph, findings, typology_chunks) is injected as `## Pre-computed evidence` in the user message; the agent synthesises directly from it and only calls MCP tools for genuine follow-ups. Dropped mandatory mermaid diagrams. Switched extractor to `list_chat_messages_full` + chronological iteration + content-hashed event ids + turn-title synthesis from `turn_message` content. Added `_log_followup_tool_calls` to record the agent's MCP usage per run. If this doc and the code disagree, trust the code, then `git blame` this file to see when it was last accurate.*
