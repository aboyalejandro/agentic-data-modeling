---
name: ai-readiness
description: Pre-merge checklist that validates dbt mart models are ready for AI consumption. Checks dbt schema quality and OpenMetadata catalog presence. Triggers include "ai readiness", "is this model ready", "checklist for", "pre-merge check".
---

# AI Readiness Checklist

Pre-merge gate that validates a dbt mart model has enough structure, documentation, and catalog presence for AI agents to consume it reliably. Runs a two-part audit (dbt files + OpenMetadata catalog), reports a checklist, and offers to auto-fix what it can.

## How It Works

1. **Parse the request** — Extract model name from `$ARGUMENTS`. Validate it against the 4 known marts (`campaign_performance`, `daily_summary`, `user_journey`, `channel_attribution`). If `$ARGUMENTS` is `all` or empty, run across all 4 models sequentially.
2. **dbt file checks** — Read `dbt/models/marts/{model}.sql` and `dbt/models/marts/_marts.yml`. Check:
   - Model has a description in YAML
   - All columns present in the SQL file are listed in the YAML
   - All columns have descriptions
   - Grain columns have `not_null` + `unique` tests (flag composite keys needing `dbt_utils.unique_combination_of_columns`)
3. **OpenMetadata checks** — Call `get_entity_details` with `entity_type: "table"` and FQN `marketing_postgres.marketing.public.{model}`. If entity not found, flag that ingestion is needed and skip remaining catalog checks. Otherwise check:
   - Table has a description
   - All columns have descriptions
   - Ownership is assigned
   - Classification tags exist
   - Freshness/profiling data is present
4. **Query guidance** — Use Postgres MCP to reverse-engineer the model's data and build query examples. This feeds directly into `enrich-metadata` descriptions. Run:
   - **Shape & grain** — `SELECT COUNT(*), COUNT(DISTINCT {grain_cols}) FROM {model}` to confirm row count matches grain definition
   - **Column profiling** — For key metric columns: NULLs, min/max, distinct counts, distributions. Focus on columns an AI agent would likely filter or aggregate on
   - **Edge case discovery** — Spot unexpected patterns: zeros vs NULLs, skewed distributions, date range gaps. These become `[Known Issues / Caveats]` in enriched descriptions
   - **Build example queries** — Write 2-3 ready-to-use SQL queries that show how an AI agent would typically consume this model (e.g., "top campaigns by ROAS last 30 days", "conversion funnel by channel"). These go in the output as a Query Examples section
5. **Report** — Print a pass/fail checklist per model, followed by the query examples section. Summarize totals: passed, auto-fixable, and manual-action items.
6. **Offer fixes** — For each fixable gap, describe the proposed fix, confirm with the user, then execute. For descriptions, incorporate findings from step 4 (edge cases, caveats) into the enrich-metadata structured format.

## Auto-Fix Rules

**Can fix** (with user confirmation):
- Missing OpenMetadata table/column descriptions → generate using enrich-metadata's structured format (read dbt SQL + YAML for context), then `patch_entity`
- Missing classification tags → add via `patch_entity`

**Cannot fix** (flag with guidance):
- Missing dbt tests → print the exact YAML snippet to add to `_marts.yml`
- Missing columns in YAML → print column stubs to add
- No ownership → flag for admin action in OpenMetadata UI
- No freshness data → flag that profiling pipeline needs enabling
- Entity not in catalog → suggest running `docker compose --profile ingestion up ingest-postgres ingest-dbt`

## MCP Tools

Three MCP servers are used in this workflow:

- **Postgres MCP** — Run SQL queries against `localhost:5432` to validate column coverage, profile data distributions, discover edge cases, and build example queries for AI consumption.
- **`get_entity_details`** — Read from OpenMetadata. Use `entity_type: "table"` and the fully qualified name (e.g., `marketing_postgres.marketing.public.daily_summary`) to get the current description, columns, tags, and ownership.
- **`patch_entity`** — Write to OpenMetadata using JSONPatch format:
  - Table description: `[{"op": "add", "path": "/description", "value": "..."}]`
  - Column description: `[{"op": "add", "path": "/columns/{index}/description", "value": "..."}]`
  - Tags: `[{"op": "add", "path": "/tags/0", "value": {"tagFQN": "...", "source": "Classification"}}]`

## Argument Parsing

- `$ARGUMENTS` = `campaign_performance` → checklist for that model
- `$ARGUMENTS` = `all` or empty → checklist for all 4 marts

## Grain Detection

Hardcoded grain map for the 4 known models:

- `campaign_performance` → composite key: `campaign_id` + `date` (needs `dbt_utils.unique_combination_of_columns`)
- `daily_summary` → single key: `date`
- `user_journey` → single key: `user_id`
- `channel_attribution` → single key: `channel`

## Output Format

Structured checklist per model:

```
## campaign_performance — AI Readiness

### dbt Schema
- [x] Model has description
- [x] All SQL columns in YAML (26/26)
- [ ] All columns have descriptions
- [ ] Grain has uniqueness tests → suggest dbt_utils.unique_combination_of_columns

### OpenMetadata Catalog
- [x] Entity exists
- [ ] Table has description
- [ ] 14/26 columns missing descriptions
- [ ] No ownership assigned
- [x] Tags present
- [ ] No freshness data

### Query Guidance
Grain check: 1,234 rows, 1,234 distinct campaign_id+date combos ✓
Edge cases found:
- spend has 0s (not NULLs) on inactive days — COALESCE in SQL
- roas is NULL when spend = 0 (division guard)

Example queries for AI agents:
1. Top 10 campaigns by ROAS last 30 days:
   SELECT campaign_name, channel, roas FROM campaign_performance
   WHERE date >= CURRENT_DATE - 30 AND spend > 0 ORDER BY roas DESC LIMIT 10

2. Daily spend trend by channel:
   SELECT date, channel, SUM(spend) FROM campaign_performance
   GROUP BY date, channel ORDER BY date

3. Campaigns with high CTR but low conversions:
   SELECT campaign_name, ctr, total_conversions FROM campaign_performance
   WHERE ctr > 0.05 AND total_conversions < 5

PASS: 4/9 | Auto-fixable: 2 | Manual: 3
→ Want me to fix the auto-fixable items?
```
