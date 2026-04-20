# AML Guard

An agentic AI system for Anti-Money Laundering (AML) investigation. Given a natural-language question about an entity, account, or transaction, AML Guard traverses a Neo4j knowledge graph, runs structured anomaly detection patterns, searches FATF/AUSTRAC typology documents via semantic search, and returns an evidence-backed risk verdict.

---

## What it does

- **Entity investigation** — pulls the full subgraph for any entity: accounts, transactions, ownership chains, jurisdiction links, and associated persons
- **Anomaly detection** — runs named graph patterns (transaction structuring, layered ownership, PEP association, high-risk jurisdictions, and more) against the live graph
- **Typology matching** — semantically searches FATF and AUSTRAC guidance documents to link observed behaviour to known financial crime typologies
- **Risk verdicts** — returns `HIGH_RISK`, `MEDIUM_RISK`, `LOW_RISK`, or `CLEARED` with a 0–1 risk score, structured findings, and cited evidence
- **Audit trail** — persists every assessment, finding, and reasoning step to the graph (Layer 3) for downstream review

---

## Architecture

### Three-layer Neo4j knowledge graph

| Layer | Contents |
|---|---|
| **Layer 1** | AML entity graph: entities, accounts, transactions, alerts, jurisdictions and their relationships |
| **Layer 2** | Typology documents: FATF Recommendations and AUSTRAC guidance parsed into Section → Indicator → Chunk nodes, with vector embeddings for semantic search |
| **Layer 3** | Runtime assessments: `CaseAssessment`, `RiskFinding`, and `InvestigationStep` nodes written by the agent during each investigation |

### Single-agent pipeline

```
User question
    ↓
AMLAgent (claude-sonnet-4-6, tool-use API)
    ├─ traverse_entity_network     — pull entity subgraph
    ├─ detect_graph_anomalies      — run anomaly patterns
    ├─ retrieve_typology_chunks    — semantic search over FATF/AUSTRAC docs
    └─ persist_case_finding        — write results to Layer 3
    ↓
AMLRiskResponse
    ├─ verdict + risk_score
    ├─ findings (severity-sorted)
    ├─ triggered typologies
    ├─ cited sections + chunks
    └─ recommended actions
```

---

## Tech stack

| Component | Technology |
|---|---|
| Agent model | Claude Sonnet (claude-sonnet-4-6), temperature 0 |
| Graph database | Neo4j AuraDB (managed cloud) |
| Embeddings | OpenAI text-embedding-3-small (1536 dims, cosine similarity) |
| Tool use | Anthropic tool-use API + FastMCP |
| UI | Streamlit |
| Data pipeline | Jupyter notebooks |

---

## Project structure

```
aml-guard/
├── src/
│   ├── agent/
│   │   ├── aml_agent.py       # Single agentic investigation loop
│   │   ├── dispatcher.py      # Tool execution dispatcher
│   │   ├── config.py          # Models, limits, constants
│   │   ├── utils.py           # Retry, truncation, history trimming
│   │   └── _security.py       # Prompt injection defence
│   ├── graph/
│   │   ├── connection.py      # Neo4j AuraDB driver wrapper
│   │   └── queries.py         # Parameterised Cypher helpers (by layer)
│   ├── mcp/
│   │   ├── schema.py          # GRAPH_SCHEMA_HINT, ANOMALY_REGISTRY, dataclasses
│   │   ├── tool_defs.py       # Tool definitions passed to Claude
│   │   ├── tools_impl.py      # Plain Python tool implementations
│   │   └── server.py          # FastMCP server registration
│   └── document/
│       ├── config.py          # document_config.yaml loader
│       ├── pdf_utils.py       # PDF text extraction
│       └── utils.py           # Streaming Claude calls, JSON parsing
├── data/
│   ├── layer_1/
│   │   ├── entities/          # Entity CSVs (see SCHEMA.md)
│   │   └── links/             # Relationship CSVs (see SCHEMA.md)
│   ├── layer_2/
│   │   ├── regulatory_documents/  # FATF/AUSTRAC PDFs (drop here)
│   │   ├── extracted/             # Notebook output CSVs
│   │   └── document_config.yaml   # Controls which PDFs are processed
│   └── layer_3/               # Runtime — written by agent, not committed
├── notebooks/
│   ├── 111_load_layer1_entities.ipynb
│   ├── 211_extract_typologies.ipynb
│   ├── 212_merge_typologies.ipynb
│   ├── 213_chunk_typologies.ipynb
│   ├── 214_embed_chunks.ipynb
│   ├── 215_validate_layer2.ipynb
│   ├── 311_agent_setup.ipynb
│   ├── 312_test_tools.ipynb
│   ├── 313_agent_demo.ipynb
│   └── 314_reset_layer3.ipynb
├── scripts/
│   └── load_layer1_entities.py  # CLI version of notebook 111
├── tests/
├── app.py                     # Streamlit chat UI
└── requirements.txt
```

---

## Setup

**1. Clone and install dependencies**

```bash
cd aml-guard
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, OPENAI_API_KEY, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
```

**3. Load data**

- Place entity CSVs in `data/layer_1/entities/` and `data/layer_1/links/` (see `SCHEMA.md` in each directory)
- Run the loader script (or the equivalent notebook):

```bash
python scripts/load_layer1_entities.py
# To wipe Layer 1 before reloading:
python scripts/load_layer1_entities.py --reset
```

**4. Load typology documents**

- Place FATF/AUSTRAC PDFs in `data/layer_2/regulatory_documents/`
- Register them in `data/layer_2/document_config.yaml`
- Run notebooks 211 → 215 in order

**5. Verify tools**

```bash
jupyter lab notebooks/311_agent_setup.ipynb
# Then run 312_test_tools.ipynb
```

**6. Run the UI**

```bash
streamlit run app.py
```

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

New patterns can be added by appending an `AnomalyPattern` entry to `ANOMALY_REGISTRY` in `src/mcp/schema.py` — no other code changes required.

---

## Adding new typology documents

1. Place the PDF in `data/layer_2/regulatory_documents/`
2. Add an entry to `data/layer_2/document_config.yaml`
3. Re-run notebooks 211 → 215

No code changes needed.

---

## Security

- **Prompt injection defence** — all tool results are wrapped in `[TOOL DATA]` structural framing; nine regex patterns detect common injection attempts and log warnings
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
