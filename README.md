# 🤖 End To End Agentic Data Modeling: Using AI and OpenMetadata MCP for Impact Analysis

A complete, self-contained data analytics stack that automatically:
- Seeds marketing data from S3 into local PostgreSQL
- Runs dbt transformations to create analytics models
- Configures Metabase with pre-loaded database connections and metadata
- Provides unified metadata management via OpenMetadata
- Enables AI-powered data exploration through Claude

## 🔗 Unified Metadata with OpenMetadata

**OpenMetadata** serves as a unified metadata platform that easily connects different parts of the data engineering cycle. It acts as a central hub to:
- Ingest metadata from data sources, transformation tools (dbt), and visualization layers
- Build end-to-end lineage showing data flow from source tables → dbt models → dashboards
- Centralize documentation, schemas, column descriptions, and relationships
- Track dependencies and understand the downstream impact of changes

This provides a complete view of our data ecosystem, enabling you to explore metadata, view lineage, and understand dependencies across all your data assets.

## 💬 End To End Data Modeling with Claude & MCP Servers

This project connects Claude to the data stack through **two MCP servers**, giving AI direct access to both metadata intelligence and raw data:

| MCP Server | Purpose | Key Tools |
|---|---|---|
| **OpenMetadata MCP** | Metadata catalog — lineage, search, glossaries, entity details | `search_metadata`, `get_entity_lineage`, `get_entity_details`, `create_glossary_term` |
| **PostgreSQL MCP** | Direct database access — query data, profile columns, validate models | `execute_sql`, `list_tables`, `list_table_stats` |

The **PostgreSQL MCP** uses [Google GenAI Toolbox](https://github.com/googleapis/genai-toolbox) (pre-downloaded binary in `bin/toolbox`) to give Claude direct SQL access to the local PostgreSQL instance. This enables data profiling, edge case discovery, and validation queries — capabilities used heavily by the AI Readiness skill.

The **OpenMetadata MCP** connects to the OpenMetadata server's native MCP endpoint, providing metadata search, lineage tracing, and glossary management through natural language.

Both servers are configured in `.mcp.json` at the project root, with permissions managed in `.claude/settings.local.json`.

### What this enables

- **Natural Language Queries**: Ask questions about your data architecture in plain English, such as "What tables feed into the `campaign_performance` model?" or "Show me all dashboards that use user data"
- **Intelligent Exploration**: Discover relationships and dependencies without manually navigating through the UI
- **Documentation Assistance**: Get instant answers about column meanings, data types, and business context
- **Lineage Visualization**: Understand data flows through conversational queries rather than complex graph navigation
- **Data Profiling**: Query the database directly to discover NULLs, distributions, edge cases, and grain violations
- **Impact Analysis**: Quickly identify what would be affected by changes to specific tables or models

## 🛠️ Claude Code Skills

The project includes four custom **Claude Code skills** (in `.claude/skills/`) that encode repeatable data engineering workflows as slash commands. These skills combine the OpenMetadata and PostgreSQL MCP tools with local file analysis to automate common tasks:

### `/metadata-impact-analysis`
Analyze downstream impact before making schema changes. Traces lineage through dbt models and dashboards to identify what breaks if a column is renamed, dropped, or its type changes.

### `/metadata-ai-readiness`
Audit and enrich dbt mart models for AI consumption. Checks schema quality, queries the database to discover edge cases, validates OpenMetadata catalog presence, and writes fixes back to dbt YAML.

### `/metadata-glossary`
Manage an OpenMetadata glossary derived from dbt models. Parses dbt YAML for column names and descriptions, groups them into business categories, and creates/syncs glossary terms via OpenMetadata.

### `/metadata-enrich`
Audit and fill missing or drifted descriptions across all dbt layers (raw sources, staging, intermediate, marts). Produces a full coverage report classifying every table and column as OK, Drift (dbt YAML written but not synced to OpenMetadata), or Missing. For any chosen table, generates layer-appropriate descriptions, presents them for review and editing, then writes confirmed descriptions to dbt YAML first (source of truth) before patching OpenMetadata. Supports per-table enrichment and batch mode (`all staging`, `all intermediate`, `all marts`).

Trigger phrases: `enrich metadata`, `which tables have no description`, `fill metadata`, `generate descriptions`, `missing descriptions`.

## 🤖 Slack Bot

The project includes a Slack bot (`slack-bot/`) that brings the catalog assistant and all four skills directly into Slack. Mention the bot in any channel or reply in a thread to ask questions or trigger enrichment workflows.

```
@databot which tables have no description?
@databot what columns does campaign_performance have?
@databot enrich user_journey
@databot what feeds into campaign_performance?
```

**How it works:** The bot uses Claude (claude-sonnet-4-6) with tool calling against the OpenMetadata REST API and the local dbt YAML files. It detects intent from the message, applies the matching skill workflow, and handles multi-step flows (audit → generate → review → confirm → apply) through Slack thread replies. Write operations always require explicit `confirm` before any file or catalog changes are made.

See [QUICKSTART.md](QUICKSTART.md#slack-bot-setup) for setup instructions.
## 📚 Documentation

This project includes comprehensive documentation to help you get started:

- **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup guide to get the entire stack running locally, including:
  - Docker environment setup (PostgreSQL, dbt, Metabase, OpenMetadata)
  - Metadata ingestion configuration
  - Claude Code MCP server connection

- **[DEMO.md](DEMO.md)** - Real-world use case demonstrations showing how AI + OpenMetadata enables:
  - Impact analysis before schema changes
  - Data discovery and validation
  - Lineage exploration and data provenance
  - Ownership and governance queries
  - AI readiness audits — enriching dbt models for AI consumption
  - Glossary management — deriving business terms from dbt into OpenMetadata
  - Slack bot — catalog Q&A and skill workflows directly in Slack

Start with the [Quick Start Guide](QUICKSTART.md) to set up your environment, then explore the [Demo Use Cases](DEMO.md) to see what's possible!

---

## 🏗️ Project Architecture & Structure

- **Data Source**: PostgreSQL database
- **Transformation**: [dbt](https://www.getdbt.com/) for data modeling and transformation.
- **Visualisation**: [Metabase](https://www.metabase.com/) dashboards for business intelligence
- **Metadata Management**: [OpenMetadata](https://open-metadata.org/) to unify all metadata in one platform (hosted locally)
- **AI Integration**: OpenMetadata MCP + PostgreSQL MCP to connect with Claude Code and enable natural language queries, data profiling, and automated workflows via custom skills

![Architecture](images/architecture.png)

This setup enables a complete data analytics workflow where:
1. Raw data flows from PostgreSQL
2. dbt transforms and models the data locally
3. Metabase provides interactive dashboards
4. OpenMetadata centralizes metadata from all components via **YAML-based ingestion** (not UI), providing unified lineage and metadata views
5. Claude connects via two MCP servers (OpenMetadata + PostgreSQL) for metadata exploration and direct data access
6. Custom skills (`/metadata-impact-analysis`, `/metadata-ai-readiness`, `/metadata-glossary`, `/metadata-enrich`) automate repeatable data engineering workflows

**Key Feature:** All OpenMetadata ingestion is configured through YAML files, enabling Infrastructure as Code (IaC) practices. Ingestion runs on-demand using Docker Compose profiles, giving you control over when metadata is synchronized. While OpenMetadata provides a UI for configuration, this project uses YAML files for version control, automation, and reproducibility.

```text
├── .claude/                        # Claude Code configuration
│   ├── settings.local.json         # MCP permissions & server config
│   └── skills/                     # Custom Claude Code skills
│       ├── metadata-impact-analysis/
│       ├── metadata-ai-readiness/
│       ├── metadata-glossary/
│       └── metadata-enrich/
├── slack-bot/                      # Slack bot — catalog Q&A and skills via Slack
│   ├── bot.py                      # Slack Bolt app (Socket Mode)
│   ├── agent.py                    # Claude agent with tool calling + skill routing
│   ├── om_client.py                # OpenMetadata REST client
│   ├── yaml_tools.py               # dbt YAML read/write (safe path handling)
│   ├── requirements.txt
│   └── .env.example
├── .mcp.json                       # MCP server definitions (Postgres + OpenMetadata)
├── bin/
│   └── toolbox                     # Google GenAI Toolbox binary (Postgres MCP)
├── dbt/                            # dbt project
│   ├── models/
│   │   ├── staging/                # 4 staging views
│   │   ├── intermediate/           # 6 intermediate views
│   │   └── marts/                  # 4 mart tables (primary analytics)
│   ├── dbt_project.yml
│   └── profiles.yml
├── images/                         # Architecture diagrams & demo screenshots
├── openmetadata/
│   ├── docker-compose.yml          # Main orchestration file
│   └── ingestion-configs/          # YAML-based ingestion configs
├── seed/                           # Data seeding scripts
│   ├── Dockerfile
│   ├── requirements.txt
│   └── scripts/                    # Scripts to seed Postgres and Metabase
├── README.md                       # Project overview and architecture
├── QUICKSTART.md                   # Step-by-step setup guide
└── DEMO.md                         # Use case demonstrations
```
