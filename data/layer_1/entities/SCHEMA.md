# Layer 1 — Entity CSV Schema

Place CSV files in this directory. The loader notebook (111_load_layer1_entities.ipynb) reads
whatever files are listed in the LOAD_MANIFEST below and ingests them into Neo4j.

---

## Required CSV files

### entities.csv
Represents natural persons and legal entities.

| Column | Type | Description |
|---|---|---|
| entity_id | string | Unique ID, e.g. `ENT-0001` |
| name | string | Full legal name |
| type | string | `individual` or `corporate` |
| risk_tier | string | `high`, `medium`, or `low` |
| is_pep | boolean | Politically Exposed Person flag |
| sanctions_match | boolean | Matches a sanctions list |
| kyc_status | string | `verified`, `pending`, or `failed` |
| country | string | ISO 3166-1 alpha-2 country code |
| date_of_birth | date (YYYY-MM-DD) | Individuals only — leave blank for corporates |
| registration_number | string | Corporates only — leave blank for individuals |
| nationality | string | ISO country code |

### accounts.csv
Bank accounts linked to entities.

| Column | Type | Description |
|---|---|---|
| account_id | string | Unique ID, e.g. `ACCT-0001` |
| entity_id | string | FK → entities.csv |
| bank_name | string | |
| account_type | string | `current`, `savings`, `correspondent`, etc. |
| currency | string | ISO 4217 (e.g. `AUD`, `USD`) |
| country | string | ISO 3166-1 alpha-2 |
| opened_date | date | |
| status | string | `active` or `closed` |
| average_monthly_balance | float | In account currency |

### transactions.csv
Financial transactions between accounts.

| Column | Type | Description |
|---|---|---|
| transaction_id | string | Unique ID, e.g. `TXN-0001` |
| from_account_id | string | FK → accounts.csv |
| to_account_id | string | FK → accounts.csv |
| amount | float | Transaction amount |
| currency | string | ISO 4217 |
| date | date | Transaction date |
| type | string | `cash_deposit`, `wire_transfer`, `internal`, etc. |
| description | string | Narrative |
| flagged_suspicious | boolean | Pre-flagged by source system |
| country_of_origin | string | ISO 3166-1 alpha-2 |
| country_of_destination | string | ISO 3166-1 alpha-2 |

### alerts.csv
AML alerts raised against entities.

| Column | Type | Description |
|---|---|---|
| alert_id | string | Unique ID, e.g. `ALERT-0001` |
| entity_id | string | FK → entities.csv |
| alert_type | string | `structuring`, `pep`, `sanctions`, `rapid_movement`, etc. |
| severity | string | `HIGH`, `MEDIUM`, or `LOW` |
| status | string | `open`, `closed`, or `escalated` |
| created_at | datetime (ISO 8601) | |
| description | string | Free text |

### jurisdictions.csv
Reference table of jurisdictions.

| Column | Type | Description |
|---|---|---|
| jurisdiction_id | string | e.g. `JUR-AU`, `JUR-VU` |
| name | string | |
| country | string | ISO 3166-1 alpha-2 |
| fatf_status | string | `member`, `non-member`, `blacklist`, or `greylist` |
| aml_risk_rating | string | `low`, `medium`, or `high` |

---

## Notes for your teammate

- All ID columns must be globally unique across the dataset.
- Date format: YYYY-MM-DD. Datetime format: ISO 8601 (YYYY-MM-DDTHH:MM:SS).
- Boolean values: use `true` / `false` (lowercase).
- Floating-point amounts: use `.` as decimal separator, no thousands separator.
- Leave optional columns blank (empty string) rather than using NULL or N/A.
- If adding new node types not listed here, update `src/mcp/schema.py` (GRAPH_SCHEMA_HINT)
  and `src/graph/queries.py` before loading.
