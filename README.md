# AML Guard

An agentic AI system for Anti-Money Laundering (AML) investigation. Given a natural-language question about an entity, AML Guard traverses a Neo4j knowledge graph, runs structured anomaly detection patterns, searches FATF/AUSTRAC typology documents via semantic search, and returns an evidence-backed risk verdict.

---

## What it does

- **Entity investigation** — pulls the full subgraph for any entity: accounts, transactions, ownership chains, jurisdiction links, and associated persons
- **Anomaly detection** — runs named graph patterns (transaction structuring, layered ownership, PEP association, high-risk jurisdictions, and more) against the live graph
- **Typology matching** — semantically searches FATF and AUSTRAC guidance documents to link observed behaviour to known financial crime typologies
- **Risk verdicts** — returns `HIGH_RISK`, `MEDIUM_RISK`, `LOW_RISK`, or `CLEARED` with a 0–1 risk score, structured findings, and cited evidence
- **Narrative synthesis** — Phase 1 LLM post-processor rewrites headlines, summaries, and finding descriptions into analyst-grade prose
- **Deep analysis** — Phase 2 agentic loop (opt-in) re-investigates the case with full tool access and produces its own verdict with a band-distance guardrail

---

## Architecture

### Three-layer Neo4j knowledge graph

| Layer | Contents |
|---|---|
| **Layer 1** | AML entity graph: entities, accounts, transactions, alerts, jurisdictions and their relationships |
| **Layer 2** | Typology documents: FATF and AUSTRAC guidance parsed into Section → Indicator → Chunk nodes with vector embeddings |
| **Layer 3** | Runtime assessments: `CaseAssessment`, `RiskFinding`, and `InvestigationStep` nodes written per investigation |

### Two-phase pipeline

```
POST /api/investigate
    ↓
Deterministic trunk (assembler.py)
    ├─ traverse_entity_network     — pull entity subgraph from Neo4j
    ├─ detect_graph_anomalies      — run anomaly registry patterns
    └─ retrieve_typology_chunks    — semantic search over Layer 2
    ↓
Phase 1 — Narrator (narrator.py, always-on when AML_USE_AGENT_NARRATIVE=1)
    └─ H2OGPTe LLM rewrites headline / summary / finding descriptions / actions
       (never mutates verdict or risk_score)
    ↓
CaseAssessment response

POST /api/investigate/deep   (opt-in)
    ↓
Phase 2 — AML Agent (aml_agent.py)
    └─ H2OGPTe agentic loop with FastMCP tool access
       owns verdict / risk_score / headline / summary / actions
       band-distance guardrail: agent verdict must be within 1 band of trunk
```

---

## Tech stack

| Component | Technology |
|---|---|
| Agent runtime | H2OGPTe (agentic loop + RAG) |
| Agent model | claude-sonnet-4-6, temperature 0.5 |
| Narrator model | H2OGPTe auto (temperature 0.2) |
| Graph database | Neo4j AuraDB |
| Embeddings | BGE-large-en-v1.5 via H2OGPTe |
| Tool protocol | FastMCP (local MCP server, zipped and uploaded to H2OGPTe) |
| Backend API | FastAPI + uvicorn |
| Frontend | Next.js + Tailwind CSS |
| Observability | h2ogpte-observability (OpenTelemetry) |

---

## Project structure

```
aml-guard/
├── src/
│   ├── api/
│   │   ├── main.py            # FastAPI app, AMLAgent singleton, deep-analysis endpoints
│   │   ├── assembler.py       # Deterministic trunk: subgraph + anomalies + typology search
│   │   ├── narrator.py        # Phase 1: H2OGPTe narrative post-processor
│   │   ├── merge.py           # Phase 2: merge agent verdict with trunk (band-distance guardrail)
│   │   └── jobs.py            # Async deep-analysis job registry + phase streaming
│   ├── agent/
│   │   ├── aml_agent.py       # Phase 2 H2OGPTe agentic loop
│   │   ├── dispatcher.py      # MCP tool execution dispatcher
│   │   ├── config.py          # Models, limits, constants
│   │   ├── utils.py           # Retry wrapper, truncation, history trimming
│   │   └── _security.py       # Prompt injection defence
│   ├── core/
│   │   ├── client.py          # H2OGPTe client factory
│   │   ├── setup.py           # Collection, chat session, MCP upload/ingest, agent keys
│   │   ├── config.py          # agents.yaml loader
│   │   └── prompt_loader.py   # Markdown prompt loader
│   ├── mcp/
│   │   ├── schema.py          # ANOMALY_REGISTRY, GRAPH_SCHEMA_HINT, dataclasses
│   │   ├── tools_impl.py      # Plain Python tool implementations
│   │   ├── server.py          # FastMCP server registration
│   │   └── bundle.py          # Builds aml_guard_mcp.zip (run after editing src/mcp/)
│   ├── graph/
│   │   ├── connection.py      # Neo4j driver wrapper
│   │   └── queries.py         # Parameterised Cypher helpers
│   ├── prompts/
│   │   ├── aml_sys.md         # Phase 2 agent system prompt
│   │   ├── aml_message.md     # Phase 2 agent user message template
│   │   ├── aml_narrative_sys.md     # Phase 1 narrator system prompt
│   │   └── aml_narrative_message.md # Phase 1 narrator user message template
│   └── document/              # PDF extraction utilities (Layer 2 pipeline)
├── web/                       # Next.js frontend
│   ├── app/investigate/       # Investigation page
│   ├── components/            # React components (VerdictBanner, FindingsList, etc.)
│   ├── lib/api.ts             # API client + SSE streaming
│   └── mocks/                 # Offline mock response (nielsen-enterprises.json)
├── config/
│   └── agents.yaml            # H2OGPTe agent config (model, timeouts, tools)
├── data/
│   ├── layer_1/               # Entity + relationship CSVs
│   ├── layer_2/               # Regulatory PDFs + extracted chunks
│   └── layer_3/               # Runtime assessments (not committed)
├── notebooks/                 # Data pipeline notebooks (111, 211–213, 311–314)
├── scripts/                   # CLI equivalents of notebooks
├── docs/
│   └── AGENT_INTEGRATION.md   # Deep-dive: phase table, merge ownership, gotchas
└── requirements.txt
```

---

## Setup

**1. Clone and install dependencies**

> `.venv` is managed by `uv`. Do not use `pip install`.

```bash
cd aml-guard
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Required variables:

```bash
H2OGPTE_API_KEY=...
H2OGPTE_ADDRESS=https://your-h2ogpte-instance
NEO4J_URI=bolt+ssc://...
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
OPENAI_API_KEY=...          # used for Layer 2 embedding pipeline
ANTHROPIC_API_KEY=...       # optional, used for legacy direct-call path
AML_USE_AGENT_NARRATIVE=1   # enables Phase 1 narrator
```

Optional observability:

```bash
OTEL_SERVICE_NAME=aml-guard
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318   # omit to print spans to stderr
```

**3. Load data**

```bash
# Layer 1 — entity graph
python scripts/load_layer1_entities.py

# Layer 2 — typology documents
# Place PDFs in data/layer_2/regulatory_documents/
# Register in data/layer_2/document_config.yaml
# Then run:
python scripts/ingest_layer2.py
python scripts/embed_chunks.py
python scripts/validate_layer2.py
```

Or run the equivalent notebooks: `111`, `211` → `213`.

---

## Running the app

- Place FATF/AUSTRAC PDFs in `data/layer_2/regulatory_documents/`
- Register them in `data/layer_2/document_config.yaml`

```bash
python scripts/ingest_layer2.py --reset
python scripts/embed_chunks.py 
python scripts/validate_layer2.py
```

**Terminal 1 — backend**

```bash
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```

**Terminal 2 — frontend**

```bash
cd web
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

> **Mock mode**: if `NEXT_PUBLIC_API_BASE` is not set, the frontend routes every question to `web/mocks/nielsen-enterprises.json` — useful offline, but does not exercise the backend.

---

## MCP tool development

After editing anything under `src/mcp/`, rebuild the zip and restart uvicorn:

```bash
python src/mcp/bundle.py
# then restart uvicorn
```

The stale zip is the most common cause of agent tool errors — rebuild before debugging anything else.

---

## Anomaly patterns

| Pattern | Severity | Description |
|---|---|---|
| `transaction_structuring` | HIGH | Multiple sub-threshold deposits into the same account from distinct sources |
| `rapid_fund_movement` | HIGH | Funds received and moved out within 48 hours with little residual balance |
| `layered_ownership` | HIGH | Multi-hop ownership chains (depth ≥ 2) obscuring beneficial owners |
| `high_risk_jurisdiction` | HIGH | Entities linked to FATF blacklisted or greylisted jurisdictions |
| `pep_association` | HIGH | Entity is a PEP or directly associated with one |
| `smurfing` | HIGH | Aggregated sub-threshold deposits across multiple accounts for the same entity |

To add a new pattern: append an `AnomalyPattern` entry to `ANOMALY_REGISTRY` in `src/mcp/schema.py`, then rebuild the MCP zip. No other code changes needed.

---

## Adding new typology documents

1. Place the PDF in `data/layer_2/regulatory_documents/`
2. Add an entry to `data/layer_2/document_config.yaml`
3. Re-run `scripts/ingest_layer2.py` → `embed_chunks.py` → `validate_layer2.py`

---

## Security

- **Prompt injection defence** — tool results are wrapped in `[TOOL DATA]` structural framing; nine regex patterns detect injection attempts
- **Write protection** — `read-neo4j-cypher` blocks `MERGE`, `CREATE`, `DELETE`, `SET`, `DETACH`, `REMOVE`, `DROP` at the dispatcher level
- **Credentials** — loaded from `.env`, never logged

---

## Risk verdict reference

| Verdict | Meaning |
|---|---|
| `HIGH_RISK` | Strong indicators of financial crime — escalate for SAR filing consideration |
| `MEDIUM_RISK` | Suspicious patterns present — enhanced due diligence required |
| `LOW_RISK` | Minor indicators — monitor and document |
| `CLEARED` | No significant risk signals found |

---

## Further reading

- **Architecture deep-dive**: [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) — phase table, field ownership, merge guardrail, mock-vs-real audit, known gotchas
