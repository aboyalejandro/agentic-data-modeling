# Demo: Agentic Data Modeling with OpenMetadata MCP

This demo showcases how AI agents can interact with your data catalog through the OpenMetadata MCP (Model Context Protocol) server to answer complex data questions, perform impact analysis, and explore data lineage.

## Overview

By connecting Claude Code to OpenMetadata, you can ask natural language questions about your data warehouse and get instant, accurate answers powered by your metadata catalog. This enables:

- **Impact Analysis**: Understand downstream effects before making schema changes
- **Data Discovery**: Find and validate data sources for analysis
- **Lineage Exploration**: Trace data flows from source to dashboard
- **Governance**: Identify data owners and compliance requirements
- **AI Readiness**: Audit and enrich dbt models for AI consumption — checks schema quality, queries the database for edge cases, validates catalog presence, and writes fixes back to dbt YAML
- **Glossary Management**: Derive business terms from dbt models and maintain them as a structured glossary in OpenMetadata
- **Slack Bot**: Catalog Q&A and skill workflows directly in Slack — no terminal required

---

## Use Case 1: Impact Analysis on Schema Changes

**Prerequisite**: Configure Lineage in OpenMetadata

🎥 **[Watch: Configure Lineage in OpenMetadata](https://focusee.imobie.com/share/256e1b5661a74775aad7205f25f67672)**

**Trigger:** `/metadata-impact-analysis i need to rename total_conversions from campaign_performance model, can you check for downstream impact?`

### The Challenge
Before renaming a column in your data model, you need to understand what will break downstream. Manually tracing dependencies across dbt models, dashboards, and reports is time-consuming and error-prone.
<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>

The skill executes a sequential workflow:
1. **Confirms entity** → `search_metadata` finds `campaign_performance` and validates `total_conversions` exists (BIGINT)
2. **Traces lineage** → `get_entity_lineage` discovers downstream nodes with column-level detail
3. **Checks SQL references** → `Grep` across `dbt/models/` finds all direct column references, including models not yet in OpenMetadata lineage
4. **Checks dashboards** → reports connected Metabase dashboards from lineage

![Impact Analysis](images/demo_claude_code_impact_analysis.png)

### Result
The skill identifies that renaming `total_conversions` is **HIGH risk**:
- **2 downstream tables**: `daily_summary` (3 refs in SQL — lines 31, 36, 38) and `user_journey` (2 refs — lines 23, 30)
- **1 Metabase dashboard**: "Agentic Data Modeling Demo" (dashboard-level only)
- **Calculated KPIs break**: `conversion_rate`, `overall_cpa`, `cost_per_conversion` all depend on this column
- **Upstream origin**: `int_conversion_metrics_by_campaign` and `int_user_conversions` also define `total_conversions` — an end-to-end rename must include these

The report includes exact line numbers, YAML files to update (`_marts.yml`, `_intermediate.yml`), and flags that no owners are set on downstream assets.

> Note that Metabase integration only allows linking dashboards, so dashboard impact is limited to that granularity level.

</details>

---

## Use Case 2: Data Discovery & Validation

**Prerequisite**: Update the description on OpenMetadata

![Target Revenue Description](images/demo_metabase_dashboard_target_revenue_description.png)

**Question:** *"Is target revenue chart on Metabase considering TV and Radio?"*

### The Challenge
Business users often ask: "What data is included in this dashboard?" Answering requires understanding chart definitions, SQL queries, and upstream data sources.

<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>
Claude Code queries OpenMetadata to:
1. Search for the "Target Revenue" chart in Metabase
2. Read the chart's description and metadata
3. Check upstream lineage to see source tables
4. Validate what data is actually included

![Target Revenue Chart Discovery](images/demo_claude_code_target_revenue.png)

### Result
**Answer: No**, the Target Revenue chart does **NOT** include TV and Radio data. The chart explicitly documents:
> "Note: we don't have information on traditional media (TV, Radio) so breaking down revenue by those channels is not supported."

The chart only uses data from the `campaigns_daily` table, which tracks digital advertising channels.

</details>

---

## Use Case 3: Lineage Exploration

**Question:** *"What tables feed into `user_journey` model?"*

### The Challenge
Understanding data lineage is critical for debugging, impact analysis, and data quality investigations. Manually tracing dependencies through dbt DAGs and SQL is tedious.


<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>
Claude Code leverages OpenMetadata's lineage tracking to:
- 1. Find the `user_journey` model
- 2. Trace upstream dependencies through intermediate models
- 3. Identify source tables
- 4. Visualize the complete data flow

![dbt Lineage](images/demo_dbt_lineage.png)
![dbt Lineage](images/demo_openmetadata_lineage.png)

### Result
The `user_journey` model is built from **2 direct upstream tables**:
- `int_user_touchpoint_summary` - User interaction metrics
- `int_user_conversions` - Conversion metrics

Which ultimately trace back to **2 source tables**:
- `attribution_touchpoints` - Multi-touch attribution data
- `conversions` - Purchase events

The agent provides both the immediate dependencies and the full lineage tree, making it easy to understand data provenance.

</details>

---

## Use Case 4: Ownership & Governance

**Prerequisite**: Create a Team and update ownership of the Metabase Dashboard on OpenMetadata

![Dashboard Owner Classification](images/demo_metabase_dashboard_owner_classification.png)

**Question:** *"Who owns the Agentic Data Modeling Demo dashboard?"*

### The Challenge
In large organizations, knowing who owns specific data assets is essential for:
- Getting approval for changes
- Reporting data quality issues
- Understanding compliance requirements


<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>
Claude Code queries OpenMetadata for ownership information:

![Owner Query](images/demo_claude_code_owner.png)

### Result
The agent can quickly identify the dashboard owner and any associated teams or governance classifications, streamlining collaboration and accountability.
</details>

---

## Use Case 5: AI Readiness — Audit, Enrich & Validate

**Prerequisite**: Postgres MCP and OpenMetadata MCP servers configured in `.mcp.json`

**Trigger:** `/metadata-ai-readiness Is user_journey ready to be consumed by an AI agent?`

### The Challenge
A model can have correct data but still be unusable by AI — missing descriptions, no tests on grain columns, gaps in the catalog. This skill audits the dbt schema, queries the database for edge cases, checks the OpenMetadata catalog, enriches dbt YAML, re-ingests, and validates the changes in the catalog.

<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>

Claude Code runs a full audit against `user_journey`:

1. **Checks dbt schema** → descriptions, column coverage, grain tests
2. **Queries the database** → confirms grain, profiles columns, discovers edge cases (e.g. 38% of users have zero-length journeys, `avg_cpc` is an unweighted average). Builds example queries for AI agents
3. **Checks OpenMetadata catalog** → finds 3 columns without descriptions and no ownership
4. **Enriches** → writes structured descriptions in `_marts.yml` incorporating database findings
5. **Re-ingests** → `docker compose --profile ingestion up ingest-postgres ingest-dbt`
6. **Validates** → `get_entity_details` confirms enriched descriptions are now in the catalog

![AI Readiness Audit](images/demo_claude_code_ai_readiness.png)

After the audit, the skill enriches `_marts.yml` descriptions with database-discovered caveats:

![AI Readiness Enrichment](images/demo_claude_code_ai_readiness_enrich.png)

After re-ingestion, the enriched descriptions are confirmed in the OpenMetadata catalog:

![AI Readiness Validated in OpenMetadata](images/demo_openmetadata_ai_readiness_validated.png)

### Result
The model goes from **6/8 to 7/8** readiness. Database-discovered caveats are now baked into dbt descriptions, and `get_entity_details` confirms they propagated to the catalog after re-ingestion. Ownership is flagged for manual action in OpenMetadata.

</details>

---

## Use Case 6: Glossary Management — Business Terms from dbt to OpenMetadata

**Prerequisite**: OpenMetadata MCP server configured in `.mcp.json` with write access (`create_glossary`, `create_glossary_term`)

**Trigger:** `/metadata-glossary Create a business glossary from our dbt models`

### The Challenge
Business terms like `roas`, `cpa`, `ctr` are defined per-model in dbt YAML but never surfaced as a shared vocabulary. Without a central glossary, teams interpret metrics differently and AI agents have no authoritative reference for business concepts.

<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>

Claude Code scans all dbt YAML files and builds a categorized glossary in OpenMetadata:

1. **Scans dbt YAML** → reads `_marts.yml`, `_intermediate.yml`, `_sources.yml` — extracts column names and descriptions
2. **Groups into categories** → maps terms to 6 business categories (KPIs, Attribution, User Journey, Campaign Metrics, Conversion Metrics, Session Metrics)
3. **Checks existing** → `search_metadata` to detect what already exists
4. **Creates glossary** → `create_glossary` for the parent, `create_glossary_term` for categories and individual terms
5. **Reports** → summary of created/existing/needs-update counts

![Glossary Management](images/demo_claude_code_glossary.png)

After creation, the glossary is live in OpenMetadata with all 6 categories and 24 terms:

![Glossary in OpenMetadata](images/demo_openmetadata_glossary.png)

### Result
24 business terms organized under 6 categories in OpenMetadata. Each term links back to its source dbt model(s). Run `/metadata-glossary sync` to add missing terms incrementally, or `/metadata-glossary audit` for a dry-run diff.

</details>

---

## Use Case 7: Slack Bot — Catalog Q&A and Skill Workflows in Slack

**Prerequisite**: Slack bot configured and running (`slack-bot/bot.py`) — see [QUICKSTART.md](QUICKSTART.md#slack-bot-setup)

**Trigger:** Mention `@databot` in any Slack channel

### The Challenge
The catalog and skills are powerful, but they require engineers to have Claude Code open. Business users and analysts can't easily ask questions about the data, check descriptions, or trigger enrichment workflows without a terminal. A Slack bot makes the catalog accessible to the whole team.

<details>
  <summary> <h4>✨ Click to see example interactions </h4> </summary>

The bot uses Claude with tool calling against the OpenMetadata REST API and local dbt YAML files. It detects intent from the message and routes to the appropriate skill workflow.

### Catalog Q&A

```
@databot what columns does campaign_performance have?
```
→ Bot calls `get_entity_details`, returns a formatted table of columns, data types, and descriptions.

```
@databot what feeds into campaign_performance?
```
→ Bot calls `get_entity_lineage`, traces upstream tables (`int_session_metrics_by_campaign`, `int_conversion_metrics_by_campaign`, `campaigns_daily`) and reports the full dependency chain.

```
@databot which tables have no description?
```
→ Bot reads all dbt YAML files and checks OpenMetadata, returns a layered coverage report (OK / Drift / Missing) across all 20 tables.

### Enrichment workflow (multi-step in thread)

```
@databot enrich user_journey
```

**Step 1** — Bot reads dbt YAML + OpenMetadata, posts the review table in the thread:

```
Column            | dbt YAML | OpenMetadata | Action
user_id           | ✓        | (empty)      | SYNC
total_touchpoints | (empty)  | (empty)      | GENERATE: "Total number of marketing..."
...
Reply "confirm" to apply, or "skip {column}" to leave unchanged.
```

**Step 2** — User replies `confirm` in the thread

**Step 3** — Bot writes updated descriptions to `dbt/models/marts/_marts.yml`, patches OpenMetadata via `patch_entity`, then confirms:

```
Update complete: user_journey
- dbt/models/marts/_marts.yml: 15 fields written
- OpenMetadata: 15 columns patched
dbt YAML and OpenMetadata are now in sync.
```

### Result
The entire catalog workflow — audit, generate, review, confirm, apply — runs inside Slack threads. Engineers and analysts can interact with the data catalog without leaving Slack or opening a terminal.

</details>
