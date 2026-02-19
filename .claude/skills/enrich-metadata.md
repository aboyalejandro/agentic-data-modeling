---
name: enrich-metadata
description: Enrich OpenMetadata entity descriptions with context from your dbt project. Scoped to mart models. Queries the database to discover edge cases and undocumented business logic that SQL definitions alone cannot reveal. Triggers include "enrich", "add context to", "document this column", "update metadata for".
---

# Enrich Metadata

Push semantic context from your dbt project into OpenMetadata without leaving your IDE. Query the actual database to discover edge cases and undocumented business logic that SQL definitions alone cannot reveal.

## How It Works

1. **Parse the request** — Extract the target (model or model.column) and any explicit context from `$ARGUMENTS`. If no context is provided, default to reading dbt files.
2. **Read dbt context** — Find and read the dbt model SQL file under `dbt/models/marts/` and its corresponding YAML schema file (`_marts.yml`). Extract transformation logic, column definitions, joins, filters, and business rules relevant to the target. Trace upstream refs to understand where data comes from.
3. **Query the database** — Use Postgres MCP to run targeted validation queries against the actual data: data distributions, averages vs weighted calculations, NULL rates, mismatches between documented and actual behavior. This step is optional — skip it if the dbt SQL provides sufficient context on its own.
4. **Look up in OpenMetadata** — Call `get_entity_details` with `entity_type: "table"` and the FQN to get the current description, column list, and tags.
5. **Diff, propose, and patch** — Compare what dbt and the database reveal vs what OpenMetadata has. For each gap, draft an enriched description using the structured format below. Present the before/after to the user and ask for confirmation before writing. Then call `patch_entity` to update.

## MCP Tools

Three MCP servers are used in this workflow:

- **Postgres MCP** — Run SQL queries against `localhost:5432` to validate data behavior, compare aggregation methods, check NULL rates, and verify documented vs actual logic.
- **`get_entity_details`** — Read from OpenMetadata. Use `entity_type: "table"` and the fully qualified name (e.g., `postgres.public.daily_summary`) to get the current description, columns, and tags.
- **`patch_entity`** — Write to OpenMetadata using JSONPatch format:
  - Table description: `[{"op": "add", "path": "/description", "value": "..."}]`
  - Column description: `[{"op": "add", "path": "/columns/{index}/description", "value": "..."}]`

## Argument Parsing

Three usage patterns:

- `$ARGUMENTS` = `campaign_performance.total_conversions — only counts digital conversions, excludes TV and Radio`
  → Enrich a specific column with explicit context.

- `$ARGUMENTS` = `user_journey`
  → Enrich a full model. Read `dbt/models/marts/user_journey.sql` and `_marts.yml` to auto-generate descriptions for columns that are missing or vague.

- `$ARGUMENTS` = `campaign_performance.total_conversions`
  → Enrich a specific column by deriving context from the SQL and YAML (no explicit context provided).

Parse `$ARGUMENTS` by splitting on ` — ` (space-dash-dash-space). Left side is the target, right side (if present) is explicit context.

Split the target on `.` — first part is the model name, second part (if present) is the column name.

## Finding dbt Files

Scoped to mart models only. The 4 mart models are:
- `campaign_performance`
- `daily_summary`
- `user_journey`
- `channel_attribution`

For the model SQL file: `dbt/models/marts/{model_name}.sql`

For the YAML schema: `dbt/models/marts/_marts.yml`

Also trace upstream: read the SQL to find `{{ ref('...') }}` calls and read those models too, to understand where the data comes from.

## Description Format

All descriptions use a structured, section-based format designed for AI readability. Use plain text with bracketed section headers — no markdown formatting (OpenMetadata renders plain text).

### Table Descriptions

Four sections, each 1-2 sentences:

```
[Business Purpose]
What business question this table answers and why it exists.

[How It's Used]
Who consumes it (dashboards, teams, reports) and what decisions it drives.

[Data Grain]
What one row represents. Source lineage (which upstream models feed it).

[Known Issues / Caveats]
Exclusions, NULL handling, edge cases, or anything that could mislead a query.
```

**Example — campaign_performance table:**

```
[Business Purpose]
Aggregates daily campaign performance metrics across digital marketing channels for ROI analysis and budget allocation.

[How It's Used]
Powers the Campaign Performance dashboard in Metabase. Used by marketing team for daily reporting and channel optimization.

[Data Grain]
One row per campaign per day. Built from int_conversion_metrics_by_campaign and int_session_metrics_by_campaign.

[Known Issues / Caveats]
Only includes digital channels (paid search, social, display, email). Excludes TV, Radio, and organic/direct. Spend and conversion metrics return 0 (not NULL) for days with no activity via COALESCE.
```

### Column Descriptions

Two sections. Add [Known Issues / Caveats] only when there are real caveats worth flagging — skip it otherwise.

```
[Business Purpose]
What this column represents and what business concept it maps to.

[Known Issues / Caveats]
Exclusions, NULL handling, derivation logic that could mislead.
```

**Example — total_conversions column:**

```
[Business Purpose]
Total count of conversion events attributed to digital marketing channels. Key input for cost-per-conversion and ROI calculations.

[Known Issues / Caveats]
Only counts digital conversions (paid search, social, display, email). Excludes TV, Radio, and organic/direct. Returns 0 (not NULL) when no conversions exist via COALESCE.
```

**Example — campaign_name column (no caveats needed):**

```
[Business Purpose]
Human-readable name of the marketing campaign. Inherited from stg_campaigns_daily without transformation.
```

## Output

After patching, confirm:
- Entity name and FQN
- What changed (before → after for each field)
- Remind the user that downstream AI queries now have richer context
