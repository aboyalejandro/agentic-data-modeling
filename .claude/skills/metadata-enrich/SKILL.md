---
name: metadata-enrich
description: Audit OpenMetadata for missing or drifted descriptions across all dbt layers, generate AI descriptions grounded in real data profiles and dbt tests, match columns to glossary terms, write confirmed descriptions back to dbt YAML (source of truth), then sync to OpenMetadata via patch_entity. Triggers include "enrich metadata", "missing descriptions", "which tables have no description", "fill metadata", "generate descriptions", "update catalog", "sync descriptions".
---

# Metadata Enrichment

Audit all dbt layers for missing or drifted descriptions, generate descriptions, write confirmed changes back to **dbt YAML first** (source of truth), then sync to OpenMetadata via `patch_entity`.

## Architecture

**dbt YAML is the source of truth.** Never patch OpenMetadata without also writing to dbt YAML — otherwise the next `ingest-dbt` run overwrites the work. The flow is always: confirm → write YAML → patch OpenMetadata.

---

## How It Works

Execute steps **sequentially**.

### Step 1: Parse input

| Input | Behavior |
|---|---|
| No args / `audit` | Full coverage report across all layers (Step 2) |
| `audit {layer}` | Scoped audit: `staging`, `intermediate`, `marts`, `sources` |
| `{table_name}` | Skip to Step 3 for that specific table |
| `all {layer}` | Generate + batch confirm for all tables in a layer |

---

### Step 2: Audit — build coverage report

**Read all dbt YAML files** to discover every model and its documented descriptions:
- `dbt/models/staging/_sources.yml` → raw sources + any staging entries
- `dbt/models/intermediate/_intermediate.yml` → intermediate models
- `dbt/models/marts/_marts.yml` → mart models

Check for staging SQL files in `dbt/models/staging/` to discover `stg_*` models not in YAML.

**For each model**, call `get_entity_details` using FQN `marketing_postgres.postgres.marketing.{model}`. Compare each field against dbt YAML to classify:
- **Missing**: empty in both dbt YAML and OpenMetadata → needs generation
- **Drift**: dbt YAML has a description but OpenMetadata doesn't (or differs) → needs sync
- **OK**: both match

Build a layered report:

```
## Description Coverage

### Raw Sources
| Table | Table Desc | Columns: OK / Drift / Missing |
|---|---|---|
| campaigns_daily | OK | 12 OK / 0 drift / 2 missing |
| metadata_snapshots | OK | 6 OK / 0 drift / 9 missing |

### Staging
| Table | Table Desc | Columns: OK / Drift / Missing |
|---|---|---|
| stg_campaigns_daily | MISSING | 0 OK / 0 drift / 16 missing |
| stg_sessions | MISSING | 0 OK / 0 drift / 16 missing |

### Intermediate
| Table | Table Desc | Columns: OK / Drift / Missing |
|---|---|---|
| int_session_metrics_by_campaign | OK | 0 OK / 9 drift / 0 missing |

### Marts
| Table | Table Desc | Columns: OK / Drift / Missing |
|---|---|---|
| campaign_performance | OK | 0 OK / 26 drift / 0 missing |

### Summary
Total: 18 tables | 5 missing table desc | 17 with column gaps | X drift (dbt→OM out of sync)
```

Ask: **"Which table would you like to enrich? Or say 'all staging', 'all intermediate', 'all marts' for batch mode."**

Stop and wait for user input.

---

### Step 3: Generate descriptions

For the chosen table(s):

**3a. Gather static context:**
- Identify which dbt YAML file contains it
- Read the YAML — use existing descriptions as the base, and extract dbt tests per column
- Read the SQL file if it exists (staging, intermediate, marts — not raw sources)
- For drift columns: note current dbt description vs current OpenMetadata value

**3b. Profile the data via PostgreSQL MCP** — skip for raw source tables that are not materialised as dbt models.

Run the following queries against the actual table. Use the model name as the table name (models are materialised in the `marketing` schema):

```sql
-- Row count and per-column null rate + distinct count
SELECT
  COUNT(*) AS total_rows,
  COUNT({col}) AS non_null_count,
  ROUND(100.0 * COUNT({col}) / NULLIF(COUNT(*), 0), 1) AS non_null_pct,
  COUNT(DISTINCT {col}) AS distinct_count
FROM marketing.{table};

-- For numeric columns: range and zero split
SELECT
  MIN({col}) AS min_val,
  MAX({col}) AS max_val,
  ROUND(AVG({col})::numeric, 2) AS avg_val,
  SUM(CASE WHEN {col} = 0 THEN 1 ELSE 0 END) AS zero_count,
  SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS null_count
FROM marketing.{table};

-- For categorical / low-cardinality columns (distinct_count <= 20): top values
SELECT {col}, COUNT(*) AS freq
FROM marketing.{table}
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```

**Use profile results to enrich descriptions with:**
- Null rate: only mention if > 0% (e.g. "Nullable — 12% of rows have no value")
- Zero vs null split: mention if zeros are meaningful (e.g. "23% are zero, not null — campaigns with no spend that day")
- Value range for numeric columns (e.g. "Range: 0–48,320")
- Enumerated values for categoricals (e.g. "Values: google_ads, facebook, email, tv")
- If `non_null_pct = 100` and `distinct_count = total_rows` → flag as a unique key in description

**3c. Extract dbt test context from YAML:**

| dbt test on column | What to add to description |
|---|---|
| `not_null` | "Always populated." |
| `not_null` + `unique` | "Primary key / grain of this table. Always populated and unique." |
| `accepted_values` | "Accepted values: {list from test config}" |
| `relationships` | "Foreign key to `{referenced_table}.{referenced_column}`" |

**3d. Match columns to glossary terms:**

For every column in the table, call `search_metadata` with the column name as the query and `entity_type: "glossaryTerm"`. Match on name similarity — exact match first, then partial.

Rules:
- Only suggest a glossary link if the match confidence is high (exact name match or the glossary term name is a clear substring of the column name, e.g. `total_roas` → `ROAS`)
- If no glossary exists yet, skip this step silently — do not error
- One column can match at most one glossary term — take the best match
- Store the matched glossary term FQN (e.g. `Marketing Analytics.KPIs.ROAS`) for use in Step 4

**Generate for missing only** — do not regenerate descriptions that already exist in dbt YAML, just flag drifted ones for sync. Incorporate profile, test, and glossary findings into all generated descriptions.

**Style by layer:**
- **Raw sources**: factual — what the raw field represents in the source system; include value range or top values if profiled
- **Staging**: what was cleaned, cast, or renamed; note source field if renamed; include null rate if non-zero
- **Intermediate**: what business logic or aggregation was applied; include range and zero-split for metrics
- **Marts**: business definition in plain language; include formula for calculated metrics (e.g. "revenue / spend"); include data-driven caveats (nulls, zeros, skew); max 3 sentences

**Present for review — include a Glossary column:**

```
## Review: {table}

### Table description
| | Value |
|---|---|
| dbt YAML | (empty) |
| OpenMetadata | (empty) |
| Generated | Aggregated session metrics grouped by campaign and date. 18,432 rows. |

### Columns
| Column | Action | Generated/Sync value | Glossary |
|--------|--------|----------------------|----------|
| total_sessions | SYNC | "Total number of distinct sessions" | — |
| unique_users | GENERATE | "Count of distinct users who had at least one session. Range: 1–4,821. Always populated." | — |
| channel | GENERATE | "Marketing channel. Values: google_ads (42%), facebook (31%), email (18%), tv (9%). Always populated." | — |
| roas | GENERATE | "Return on ad spend. Calculated as revenue / spend. Range: 0.2–8.4." | → KPIs > ROAS |
| cpa | GENERATE | "Cost per acquisition. Calculated as spend / conversions. Nullable — 8% of rows have no conversions." | → KPIs > CPA |
| avg_session_duration | OK | — | — |
```

Then say: **"Reply with changes (e.g. 'change unique_users to X') or 'confirm' to apply. Say 'skip {column}' to leave a column or its glossary link unchanged."**

Stop and wait.

---

### Step 4: Apply confirmed descriptions

Once confirmed (with or without edits):

**A. Write to dbt YAML first**
Use the `Edit` tool to update the appropriate YAML file:
- Add or update `description:` under the model for table descriptions
- Add or update `description:` under each column entry
- If a column has no YAML entry yet, add it
- Preserve all existing YAML structure, tests, and formatting

**B. Match columns by name, not index**
Call `get_entity_details` to get the full column list. Find each column's array index by matching `column.name` — never assume order. Build the patch using the matched index.

**C. Patch OpenMetadata**
Build a JSON Patch array for only the fields that changed:
- Table description: `{"op": "add"/"replace", "path": "/description", "value": "..."}`
- Column descriptions: `{"op": "add"/"replace", "path": "/columns/{matched_index}/description", "value": "..."}`
- Use `"add"` if currently empty/null, `"replace"` if value exists

Call `patch_entity` with `entity_type: "table"`, the FQN, and the patch array.

**D. Apply glossary term links**
For every column that matched a glossary term in Step 3d and was not skipped by the user, add the glossary tag to the column patch:

```json
{
  "op": "add",
  "path": "/columns/{matched_index}/tags/-",
  "value": {
    "tagFQN": "{glossary_term_fqn}",
    "source": "Glossary",
    "labelType": "Automated"
  }
}
```

Include these operations in the same `patch_entity` call as the description updates — do not make a separate call. Skip glossary linking silently if the glossary term FQN no longer exists (verify with `search_metadata` before patching).

---

### Step 5: Validate

Call `get_entity_details` again. Confirm every patched field matches the confirmed value.

Report:

```
## Update Complete: {table}

### dbt YAML
- File updated: dbt/models/marts/_marts.yml
- Fields written: X

### OpenMetadata
- Table description: updated / already matched / skipped
- Columns updated: X
- Columns synced (drift fixed): Y
- Columns skipped (OK or user skipped): Z

### Glossary Links
- Linked: roas → KPIs > ROAS
- Linked: cpa → KPIs > CPA
- No match: total_sessions, unique_users, channel, avg_session_duration

dbt YAML and OpenMetadata are now in sync.
```

Ask: **"Would you like to enrich another table?"**

---

### Batch mode (`all {layer}`)

When user says `all staging`, `all intermediate`, or `all marts`:
1. Run Step 3 for ALL tables in that layer at once — show a single combined review table
2. User can edit individual cells or say `confirm all`
3. Apply Step 4 for each table sequentially
4. Show one combined Step 5 report

---

## MCP Tools

- **`search_metadata`** (read) — Two uses: (1) fallback if FQN lookup fails, (2) match column names against existing glossary terms in Step 3d
- **`get_entity_details`** (read) — Fetch descriptions + column list with indices for name matching
- **`patch_entity`** (write) — Push confirmed descriptions and glossary term links to OpenMetadata in a single call
- **`execute_sql`** (read, Postgres MCP) — Profile columns: null rates, distinct counts, value ranges, top categorical values. Used in Step 3b to ground generated descriptions in real data.

## Local Tools

- **`Read`** — Read dbt YAML and SQL files
- **`Edit`** — Write confirmed descriptions back to dbt YAML (always before patching OpenMetadata)

## Reference

**FQN pattern**: `marketing_postgres.postgres.marketing.{model}`

**dbt YAML files:**
| Layer | YAML file | SQL location |
|---|---|---|
| Raw sources | `dbt/models/staging/_sources.yml` | none |
| Staging | `dbt/models/staging/_sources.yml` | `dbt/models/staging/{model}.sql` |
| Intermediate | `dbt/models/intermediate/_intermediate.yml` | `dbt/models/intermediate/{model}.sql` |
| Marts | `dbt/models/marts/_marts.yml` | `dbt/models/marts/{model}.sql` |
