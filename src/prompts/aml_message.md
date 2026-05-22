Investigate the following and produce a risk assessment:

{question}

## Pre-computed evidence

The deterministic AML trunk has already executed the three baseline MCP tools against this entity. The structured results below ARE the source of truth for your synthesis. Reason over them directly — do NOT re-call `traverse_entity_network_tool`, `detect_graph_anomalies_tool`, or `retrieve_typology_chunks_tool` for the same scope.

You MAY call any MCP tool for follow-up if (and only if) one of the following holds:
- The subgraph reveals an `Intermediary` node that the baseline anomaly set did not scope a `detect_graph_anomalies_tool` call to.
- A rubric condition (e.g. `jurisdiction ≠ countries`, `concentrated_oversight`) is satisfied but a related pattern (`high_risk_jurisdiction`, `intermediary_shell_network`) is missing from the baseline hits.
- A retrieved typology chunk references a pattern that hasn't been verified against the subgraph.

Each follow-up call must have a one-line justification in the SUMMARY of the form: `Follow-up: <tool> scoped to <node_id> because <rubric reason>.`

### Subject

```json
{subject}
```

### Step 1 — traverse_entity_network (2-hop subgraph)

```json
{subgraph}
```

### Step 2 — detect_graph_anomalies (baseline pattern hits)

```json
{findings}
```

### Step 3 — retrieve_typology_chunks (top citations)

```json
{typology_chunks}
```
