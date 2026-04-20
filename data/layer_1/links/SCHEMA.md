# Layer 1 — Relationship CSV Schema

Place relationship CSV files in this directory. Each file defines edges between
nodes already created from the entities/ CSVs.

---

## Required CSV files

### entity_accounts.csv
`(Entity)-[:HAS_ACCOUNT]->(Account)`

| Column | Type |
|---|---|
| entity_id | string |
| account_id | string |
| role | string | `primary`, `secondary`, `beneficial_owner` |
| authorized_signatory | boolean |

### entity_jurisdictions.csv
`(Entity)-[:REGISTERED_IN|RESIDES_IN]->(Jurisdiction)`

| Column | Type | Description |
|---|---|---|
| entity_id | string | |
| jurisdiction_id | string | |
| link_type | string | `REGISTERED_IN` or `RESIDES_IN` |
| registration_number | string | Corporates only |
| residency_type | string | Individuals only: `permanent`, `temporary` |

### entity_ownership.csv
`(Entity)-[:OWNS]->(Entity)`

| Column | Type |
|---|---|
| owner_entity_id | string |
| subsidiary_entity_id | string |
| ownership_percentage | float |
| ownership_type | string | `direct`, `indirect`, `beneficial` |
| effective_date | date |

### alert_entities.csv
`(Alert)-[:RELATES_TO]->(Entity)`

| Column | Type |
|---|---|
| alert_id | string |
| entity_id | string |

---

## Notes

- All FK values must match IDs in entities/ CSVs exactly.
- The loader notebook processes this directory after entities/ — order matters.
