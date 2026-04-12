---
name: metadata-enrich
description: Audit OpenMetadata for missing or drifted descriptions across all dbt layers, generate AI descriptions, write confirmed descriptions back to dbt YAML (source of truth), then sync to OpenMetadata via patch_entity. Triggers include "enrich metadata", "missing descriptions", "which tables have no description", "fill metadata", "generate descriptions", "update catalog", "sync descriptions".
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

**Gather context:**
- Identify which dbt YAML file contains it
- Read the YAML — use existing descriptions as the base
- Read the SQL file if it exists (staging, intermediate, marts — not raw sources)
- For drift columns: show current dbt description vs current OpenMetadata value

**Generate for missing only** — do not regenerate descriptions that already exist in dbt YAML, just flag drifted ones for sync.

**Style by layer:**
- **Raw sources**: factual — what the raw field represents in the source system
- **Staging**: what was cleaned, cast, or renamed; note source field if renamed
- **Intermediate**: what business logic or aggregation was applied
- **Marts**: business definition in plain language; include formula for calculated metrics (e.g. "revenue / spend"); max 2 sentences

**Present for review:**

```
## Review: {table}

### Table description
| | Value |
|---|---|
| dbt YAML | (empty) |
| OpenMetadata | (empty) |
| Generated | Aggregated session metrics grouped by campaign and date... |

### Columns
| Column | dbt YAML | OpenMetadata | Action | Generated/Sync value |
|--------|----------|--------------|--------|----------------------|
| total_sessions | "Total number of distinct sessions" | (empty) | SYNC | "Total number of distinct sessions" |
| unique_users | (empty) | (empty) | GENERATE | "Count of distinct users who had sessions on this date." |
| avg_session_duration | "Average session duration in seconds" | "Average session duration in seconds" | OK | — |
```

Then say: **"Reply with changes (e.g. 'change unique_users to X') or 'confirm' to apply. Say 'skip {column}' to leave a column unchanged."**

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

- **`search_metadata`** (read) — Fallback if FQN lookup fails
- **`get_entity_details`** (read) — Fetch descriptions + column list with indices for name matching
- **`patch_entity`** (write) — Push confirmed descriptions to OpenMetadata

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
