# Demo: Agentic Data Modeling with OpenMetadata MCP

This demo showcases how AI agents can interact with your data catalog through the OpenMetadata MCP (Model Context Protocol) server to answer complex data questions, perform impact analysis, and explore data lineage.

## Overview

By connecting Claude Code to OpenMetadata, you can ask natural language questions about your data warehouse and get instant, accurate answers powered by your metadata catalog. This enables:

- **Impact Analysis**: Understand downstream effects before making schema changes
- **Data Discovery**: Find and validate data sources for analysis
- **Lineage Exploration**: Trace data flows from source to dashboard
- **Governance**: Identify data owners and compliance requirements
- **Metadata Enrichment**: Discover undocumented business logic by querying the database and writing enriched context back to the catalog

---

## Use Case 1: Impact Analysis on Schema Changes

**Prerequisite**: Configure Lineage in OpenMetadata

🎥 **[Watch: Configure Lineage in OpenMetadata](https://focusee.imobie.com/share/256e1b5661a74775aad7205f25f67672)**

**Question:** *"Can you do an impact analysis on changing the column `total_conversions` name of `campaign_performance` model?"*

### The Challenge
Before renaming a column in your data model, you need to understand what will break downstream. Manually tracing dependencies across dbt models, dashboards, and reports is time-consuming and error-prone.
<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>

Claude Code uses the OpenMetadata MCP to:
1. Find the `campaign_performance` model
2. Trace its downstream lineage
3. Identify which models and dashboards use the `total_conversions` column
4. Provide a comprehensive impact report

![Impact Analysis](images/demo_claude_code_impact_analysis.png)

### Result
The agent identifies that renaming `total_conversions` will break:
- **1 downstream table**: `daily_summary` (with 3 column references)
- **1 dashboard**: "Agentic Data Modeling Demo" on Metabase

This saves hours of manual investigation and prevents production incidents.

> Note that Metabase integration only allows linking dashboards, so this use case is limited to that granularity level.

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

## Use Case 5: Metadata Enrichment via Database Discovery

**Prerequisite**: Postgres MCP and OpenMetadata MCP servers configured in `.mcp.json`

**Question:** *"Can you enrich the metadata for `daily_summary`?"*

### The Challenge
The previous use cases are read-only — querying the catalog for answers. But what happens when the AI can also query the actual database? It can discover things that metadata alone can't reveal, and write those findings back to the catalog.

<details>
  <summary> <h4>✨ Click to see Claude Code output </h4> </summary>

While enriching `daily_summary`, Claude Code reads the dbt SQL and notices several `avg()` columns (`avg_cpc`, `avg_ctr`, `avg_session_duration`, etc.). To validate the descriptions it's about to write, it queries the database — and accidentally discovers a statistical caveat:

1. Reads `daily_summary.sql` and `_marts.yml` → builds context for all columns
2. Notices `avg(cpc)` pattern → queries Postgres to compare `avg_cpc` vs `total_spend / NULLIF(total_clicks, 0)`
3. The values diverge — `avg_cpc` is an unweighted average of per-campaign CPCs, not a true portfolio CPC
4. Flags the finding, writes enriched descriptions back to OpenMetadata via `patch_entity`

### Result
What started as a routine enrichment task uncovered undocumented business logic: `avg_cpc` is an **average of averages**, not volume-weighted. The same applies to `avg_ctr`, `avg_session_duration`, `avg_pages_per_session`, and `avg_order_value`. These caveats are now documented in OpenMetadata for downstream consumers.

</details>
