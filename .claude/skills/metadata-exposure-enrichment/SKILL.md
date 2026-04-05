---
name: metadata-exposure-enrichment
description: Enrich dbt exposure definitions by querying Metabase directly via MCP. Discovers dashboard cards, maps table and column references to dbt models, audits the existing _exposures.yml for gaps, and writes back a fully enriched exposure. Triggers include "enrich exposure", "exposure enrichment", "document dashboard", "update exposures", "what does the dashboard use".
---

# Exposure Enrichment

Discovers what a Metabase dashboard actually contains and writes that context back into dbt exposures. Works with Metabase MCP and Postgres MCP only, no metadata platform required.

## How It Works

1. **Parse `$ARGUMENTS`** -- Dashboard name, dashboard ID (e.g. `2`), or `all`. If empty, default to `all`. Extract any optional `--dry-run` flag (report only, no file write).
2. **Check file exists** -- Read `dbt/models/marts/_exposures.yml`. If missing, stop and output:
   > ERROR: `dbt/models/marts/_exposures.yml` not found. Create a barebones version first with `name`, `type`, `url`, and `depends_on` fields, then re-run this skill.
3. **Discover via Metabase MCP** -- Execute sequentially:
   a. `metabase-list-dashboards` -- confirm the target dashboard exists and get its ID
   b. `metabase-get-dashboard` with the dashboard ID -- extract the `dashcards` array to get all `card_id` values
   c. For each `card_id`: call `metabase-get-question` -- collect card name, display type, and `dataset_query` (MBQL `source-table` or native SQL)
   d. `metabase-get-database-metadata` for the database -- map internal Metabase table IDs to real table names in the `marketing` schema
   e. `metabase-get-current-user` -- capture email for the exposure `owner` field
4. **Cross-reference to dbt** -- For each card's source table, determine whether it maps to a dbt mart model or a raw source:
   - Read `dbt/models/marts/` SQL files and `_marts.yml` to confirm mart models
   - Read `dbt/models/staging/_sources.yml` to identify raw source tables
   - Mart models become `ref('model_name')` in `depends_on`
   - Raw source tables become `source('marketing_raw', 'table_name')` in `depends_on`
   - Flag any table that doesn't map to either
5. **Audit the existing exposure** -- Read `_exposures.yml` and check each exposure:
   - Is `description` present and non-empty?
   - Is `owner` present with name and email?
   - Is `maturity` set?
   - Does `depends_on` include ALL models/sources discovered in step 3?
   - Are card-level details documented in the description?
   - Are key columns documented?
6. **Report** -- Print a structured summary before offering any write:
   - Dashboard: name, URL, total card count
   - Card inventory: ID, name, display type, source table, columns used (aggregation + breakout)
   - Audit gaps: what `_exposures.yml` is missing vs what was discovered
   - End with: `GAPS: N fields missing | Cards: N discovered | Models: N mapped`
7. **Offer to enrich** -- Propose the enriched YAML and confirm with user before writing. If `--dry-run`, print proposed content only. On confirmation:
   - Write to `dbt/models/marts/_exposures.yml`
   - Report what changed (before vs after)

## Description Format

Plain text with bracketed headers. Same convention as `_marts.yml` descriptions. dbt YAML and OpenMetadata both render plain text.

**Exposure description**:
`[Business Purpose]` what decisions the dashboard drives and who uses it.
`[Cards]` list each card: name, chart type, what it measures.
`[Key Columns]` columns surfaced in the dashboard (aggregation columns + breakout dimensions).
`[Data Sources]` which dbt models and sources feed the dashboard, and how.
`[Known Issues / Caveats]` date range defaults, missing channels, filter behavior, archived cards.

## Reference

**Target dashboard**: "Agentic Data Modeling Demo" (ID=2), URL `http://localhost:3000/dashboard/2`

**Known card inventory on dashboard 2**:
- Card 40: ROAS (smartscalar) -- avg(roas) from campaign_performance, grouped by date
- Card 41: CR% (smartscalar) -- avg(conversion_rate) from campaign_performance, grouped by date
- Card 42: Target Revenue (progress) -- sum(total_revenue) from campaign_performance, grouped by date
- Card 43: Daily Spend by Channel (bar) -- sum(spend) from campaigns_daily, grouped by date + channel
- Card 44: Desktop Per Channel (pie) -- sum(desktop_sessions) from campaign_performance, grouped by channel
- Card 45: Mobile Per Channel (pie) -- sum(mobile_sessions) from campaign_performance, grouped by channel

**Standalone card NOT on dashboard 2** (do not include):
- Card 38: ROAS (table, native SQL) -- archived, not on any active dashboard

**Metabase table to dbt model map**:
- `campaign_performance` -> mart model, use `ref('campaign_performance')`
- `campaigns_daily` -> raw source table staged as `stg_campaigns_daily`, use `source('marketing_raw', 'campaigns_daily')`
- `daily_summary` -> mart model, not directly queried by any card but is a rollup of campaign_performance

**dbt mart models**: `campaign_performance`, `daily_summary`, `user_journey`, `channel_attribution`
**Files**: `dbt/models/marts/_exposures.yml`, `dbt/models/marts/_marts.yml`
**Sources**: `dbt/models/staging/_sources.yml` (source name: `marketing_raw`, schema: `marketing`)

## Output Format

```
## Exposure Enrichment: {dashboard_name} (ID={id})

### Dashboard Discovery
- Cards on dashboard: {count}
- Source tables: {table} ({n} cards), ...
- dbt mapping: {table} -> {ref or source}

### Card Inventory
| Card | Name | Type | Source Table | Columns Used |
|------|------|------|--------------|--------------|
| ...  | ...  | ...  | ...          | ...          |

### Audit: _exposures.yml gaps
- description: {PRESENT | MISSING}
- owner: {PRESENT | MISSING}
- maturity: {PRESENT | MISSING}
- depends_on: {complete | missing: list}
- card documentation: {PRESENT | MISSING}

### Proposed enrichment
{full enriched YAML}

GAPS: {n} fields missing | Cards: {n} discovered | Models: {n} mapped
```