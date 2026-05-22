# CLAUDE.md — aml-guard

AML investigation app: deterministic Neo4j graph trunk (subgraph traversal + anomaly registry + typology vector search) wrapped with two H2OGPTe integration paths — Phase 1 narrator (always-on rewrite, never mutates verdict) and Phase 2 deep agent (opt-in via "Run Deep Analysis", owns verdict/headline/summary/actions). Long-form architecture, phase mapping, merge ownership, and mock-vs-real audit live in [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) — read it when touching anything in `src/api/` or `src/agent/`.

## Dev environment

- **`.venv` is managed by `uv` — pip is NOT installed.** Use `uv pip install <pkg>` (binary at `/Users/hanching/.local/bin/uv`). After any install, update [requirements.txt](requirements.txt). `pip install` / `python -m pip install` will fail.
- Backend: `uvicorn src.api.main:app --reload --port 8000`.
- Frontend: `cd web && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev`. Without `NEXT_PUBLIC_API_BASE`, the frontend goes into mock mode and routes every question to `mocks/nielsen-enterprises.json` — useful offline, dishonest as a demo.
- Required `.env`: `H2OGPTE_API_KEY`, `H2OGPTE_ADDRESS`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `AML_USE_AGENT_NARRATIVE=1` (enables Phase 1).

## H2OGPTe integration rules

- **Two paths, do not conflate.** Phase 1 = wrapper on `POST /api/investigate` in [src/api/narrator.py](src/api/narrator.py) — post-processes deterministic trunk, rewrites headline/summary/finding-descriptions/actions. **Never mutates verdict or risk_score.** Phase 2 = async job triple (`POST /api/investigate/deep`, `GET .../status/{id}`, `POST .../cancel/{id}`) in [src/api/main.py](src/api/main.py) + [src/api/jobs.py](src/api/jobs.py) — real agent loop, owns verdict/headline/summary/actions with the band-distance guardrail (below).
- **`AMLAgent` is a singleton.** `Lock`-protected lazy init via `_get_agent()` in [src/api/main.py](src/api/main.py). `.setup()` is expensive (collection create + MCP upload) — do not instantiate per-request.
- **Timeouts in [config/agents.yaml](config/agents.yaml) are SECONDS, not ms.** `agent_total_timeout: 900` = 15 min; SDK auto-derives request timeout to `max(600, total + 60)` = 960s. The original mistake (`2000` read as 2s, actually 33min) cost a session. Why: H2OGPTe SDK convention; the units are not labelled in the YAML.
- **`cost_controls.max_cost` is silently ignored under `llm: "auto"`.** Real Claude Opus 4.6 runs hit $5–$15 per deep-analysis click (Coder Agent re-reads tool output multiple times → 2.5M input tokens). To cap cost, **pin** a specific model in [config/agents.yaml](config/agents.yaml) (e.g. `llm: "openai/gpt-oss-120b"` drops cost ~10×). Don't pretend `max_cost` works.
- **Rebuild the MCP zip manually after editing anything under `src/mcp/`:**
  ```bash
  python src/mcp/bundle.py     # writes src/mcp/aml_guard_mcp.zip
  ```
  Then **restart uvicorn** so the singleton agent re-uploads on next deep run. **Stale-zip is the #1 debugging footgun** — if the agent throws weird tool errors, suspect this before anything else. No CI / pre-commit hook enforces the rebuild.
- **`register_mcp_tool()` in [src/core/setup.py](src/core/setup.py) is idempotent** — deletes prior entries by `tool_name` before re-adding. Why: uvicorn `--reload` would otherwise accumulate duplicate registrations on every restart. Do not bypass.
- **Local MCP config rules** (learned over 4 rounds of debugging):
  - `enable_by_default: True` is required, else the tool stays out of the agent's runtime toolset even though it appears in listings.
  - `tool_usage_mode: 'runner'` is **invalid for `local_mcp`** (only `remote_mcp` supports it) and is silently dropped — do not set it.
  - Use `get_custom_agent_tools` for diagnostics, **not** `list_mcp_tools` (wrong API for our setup).
- **`SERVER_FILE` in [src/core/setup.py](src/core/setup.py) resolves relative to the file itself**, not CWD — safe to launch uvicorn from any directory.

## Code-change conventions

- **Narrator output is strict JSON.** Parsed in [src/api/narrator.py](src/api/narrator.py) with fence-stripping + safe-default fallback. Keep the prompt JSON-shaped — never let it go free-form. Prompts: [src/prompts/aml_narrative_sys.md](src/prompts/aml_narrative_sys.md) + [src/prompts/aml_narrative_message.md](src/prompts/aml_narrative_message.md).
- **Deep-agent output is markdown key:value.** `_parse_response()` in [src/agent/aml_agent.py](src/agent/aml_agent.py) regex-extracts `VERDICT / RISK_SCORE / SUMMARY / TRIGGERED_TYPOLOGIES / CITED_CHUNKS / RECOMMENDED_ACTIONS`. Parser is lenient — missing/malformed field → safe default. Do not switch this to JSON without rewriting the prompt + parser together. Prompt: [src/prompts/aml_sys.md](src/prompts/aml_sys.md).
- **Deterministic trunk must stay pure.** `build_case_assessment()` in [src/api/assembler.py](src/api/assembler.py) has no LLM calls and no `try/except` for H2OGPTe. All LLM coupling lives in `narrator.py` (Phase 1) or `aml_agent.py` + [src/api/merge.py](src/api/merge.py) (Phase 2). Don't inline LLM logic into the assembler — the `AML_USE_AGENT_NARRATIVE=0` byte-identical fallback depends on this.
- **Merge band-distance ≤1 guardrail** in [src/api/merge.py](src/api/merge.py): if the agent's verdict differs from the deterministic verdict by more than one band (e.g. HIGH_RISK → CLEARED), deterministic wins. Why: a parser glitch or hallucination must not silently downgrade a high-risk case. Do not remove without conscious sign-off.
- **Phase 1 flag `AML_USE_AGENT_NARRATIVE`** — when off, `/api/investigate` response must be byte-identical to the deterministic trunk. Keep the narrator a wrapper, never inline.
- **New anomaly patterns** — append an `AnomalyPattern` entry to `ANOMALY_REGISTRY` in [src/mcp/schema.py](src/mcp/schema.py). No other code changes needed. **Then rebuild the MCP zip.**
- **New typology PDFs** — drop into `data/layer_2/regulatory_documents/`, register in [data/layer_2/document_config.yaml](data/layer_2/document_config.yaml), re-run notebooks 211 → 215. No code changes.
- **Phase mapping for deep-analysis progress** is the single source of truth in `DEEP_PHASES` in [src/api/jobs.py](src/api/jobs.py). Phase index is **monotonic** — once phase 3 is reported, never report a lower phase even if a later message mentions an earlier tool (the agent may repeat tool calls). See the table in [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md).
- **Field ownership after deep analysis** (full table in [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md)): agent owns `verdict`, `risk_score`, `headline`, `summary`, `recommended_actions`, `triggered_typologies_agent`; deterministic owns `subject`, `case_id`, `subgraph`, `findings`, `typology_chunks`, `investigation_steps`, `tx_velocity`, `risk_decomposition`, `connection_focus`. Don't cross-wire.
- **Write protection** — `read-neo4j-cypher` blocks `MERGE / CREATE / DELETE / SET / DETACH / REMOVE / DROP` at the dispatcher level. Never relax this.

## Known gotchas / tech debt

- **`SessionError` import in [src/agent/utils.py](src/agent/utils.py) is fine** — verified 2026-05-21, `from h2ogpte.types import Answer, SessionError` succeeds with the installed SDK (`SessionError` is still defined in `h2ogpte/types.py`). If a future SDK bump drops it, add a `try/except ImportError` fallback that defines a local `class SessionError(Exception)` — the retry logic in `query_with_retry` will still catch SDK-raised instances because they share the same base.
- **Deep-analysis job registry is in-memory only** in [src/api/jobs.py](src/api/jobs.py). `uvicorn --reload` (triggered by any code edit during a running deep analysis) drops the registry — the agent thread keeps running and **still bills**, but the result vanishes from the UI. Acceptable for demo; switch to SQLite/Redis for production.
- **"Stop Watching" is honest, not forceful.** The H2OGPTe SDK has no abort API. Cancelling a deep job stops frontend polling and discards the result on completion, but the agent loop runs to completion server-side and **still bills**. Do not silently rename the button to "Cancel" — the wording is load-bearing.
- **"Approve & Escalate" downstream pipeline is pure client-side animation.** No agents are actually invoked, no SAR is filed. Tokens like `{caseId}` substitute from real data but the work is fake. Don't add real-sounding backend logs that imply otherwise.
- **`tx_velocity` sparkline is synthetic** — `_synth_tx_velocity()` in [src/api/assembler.py](src/api/assembler.py) is an md5-derived 12-month fingerprint. No `Transaction` nodes exist in Layer 1 yet. Do not trust it as signal; flag it as mock in any review.
- **Verification Protocol items 1–2 are static stubs** (sanctions screening, source-of-funds) — see [web/components/VerdictBanner.tsx](web/components/VerdictBanner.tsx). Items 3–4 rationale is dynamic but the cycling "thinking" sub-messages are scripted.
- **Mock mode** routes **every** question to `mocks/nielsen-enterprises.json` regardless of input — see [web/lib/mock-adapter.ts](web/lib/mock-adapter.ts). Useful offline; dishonest as a demo. Surface this if anyone proposes a client demo without the backend wired.
- **`triggered_typologies_agent`** is emitted by the deep agent but no frontend component renders it yet — present on the merged case, invisible to the user. Same for the agent's `SUBGRAPH_DIAGRAM` and `RISK_COMPOSITION` mermaid blocks (currently buried inside `summary`).

## Pointers

- **Architecture deep-dive**: [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) — phase table, merge ownership table, mock-vs-real audit, future-work backlog, full gotchas.
- **Project intro + anomaly catalog + 3-layer graph model**: [README.md](README.md).
- **Backend hot paths**: [src/api/main.py](src/api/main.py), [src/api/jobs.py](src/api/jobs.py), [src/api/narrator.py](src/api/narrator.py), [src/api/merge.py](src/api/merge.py), [src/api/assembler.py](src/api/assembler.py), [src/agent/aml_agent.py](src/agent/aml_agent.py), [src/core/setup.py](src/core/setup.py).
- **Agent config**: [config/agents.yaml](config/agents.yaml).
- **MCP**: [src/mcp/tools_impl.py](src/mcp/tools_impl.py), [src/mcp/schema.py](src/mcp/schema.py), [src/mcp/bundle.py](src/mcp/bundle.py).
- **Frontend**: [web/lib/api.ts](web/lib/api.ts), [web/app/investigate/page.tsx](web/app/investigate/page.tsx), [web/components/VerdictBanner.tsx](web/components/VerdictBanner.tsx), [web/lib/mock-adapter.ts](web/lib/mock-adapter.ts).
