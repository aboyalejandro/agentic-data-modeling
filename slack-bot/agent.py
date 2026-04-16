import json
import os
from pathlib import Path

import anthropic

import om_client
import yaml_tools

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"


def _load_skills() -> str:
    parts = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        content = skill_file.read_text()
        # Strip YAML frontmatter
        if content.startswith("---"):
            end = content.index("---", 3)
            content = content[end + 3:].strip()
        parts.append(f"### Skill: `/{skill_dir.name}`\n\n{content}")
    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT = f"""You are a data catalog assistant for a marketing analytics team running on Slack.
You have direct access to an OpenMetadata catalog and a local dbt project.

## Your capabilities
Detect the user's intent from their message and apply the appropriate skill workflow:
- Catalog Q&A — search and explain tables, columns, lineage, descriptions
- Metadata enrichment — audit missing/drifted descriptions, generate and apply them
- Glossary management — audit, create, or sync the marketing glossary
- Impact analysis — trace what breaks if a column or table changes
- AI readiness — audit dbt models for AI consumption quality

## Skills available
{_load_skills()}

## Slack behavior rules
- Keep responses concise. Use markdown (bullet points, code blocks, tables).
- Multi-step workflows (enrich, glossary) happen across thread replies — post each step, then wait.
- **Before writing any file or patching OpenMetadata**, show the user exactly what will change and wait for them to reply `confirm`. Never apply writes without explicit confirmation.
- If the user says `skip {{column}}`, exclude that column from the patch.
- After applying changes, report what was done (X fields updated, file written).
- If something fails, report the error clearly.

## FQN pattern for this project
`marketing_postgres.postgres.marketing.{{table_name}}`

## dbt YAML files
- Raw sources & staging: `dbt/models/staging/_sources.yml`
- Intermediate: `dbt/models/intermediate/_intermediate.yml`
- Marts: `dbt/models/marts/_marts.yml`
"""

TOOLS = [
    {
        "name": "search_metadata",
        "description": "Search for tables, dashboards, or other entities in the OpenMetadata catalog.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "entity_type": {
                    "type": "string",
                    "description": "Filter by entity type: table, dashboard, pipeline",
                    "enum": ["table", "dashboard", "pipeline"],
                },
                "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_entity_details",
        "description": (
            "Get full details of a table from OpenMetadata: columns, descriptions, tags. "
            "FQN format: marketing_postgres.postgres.marketing.{table_name}"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fqn": {"type": "string", "description": "Fully qualified name of the entity"},
            },
            "required": ["fqn"],
        },
    },
    {
        "name": "get_entity_lineage",
        "description": "Get upstream and downstream lineage for a table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fqn": {"type": "string", "description": "Fully qualified name of the table"},
                "depth": {"type": "integer", "description": "Lineage depth (default 2)", "default": 2},
            },
            "required": ["fqn"],
        },
    },
    {
        "name": "patch_entity",
        "description": (
            "Apply JSON Patch operations to update descriptions or tags in OpenMetadata. "
            "Only call this after the user has explicitly said 'confirm'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fqn": {"type": "string", "description": "Fully qualified name of the entity"},
                "patch": {
                    "type": "array",
                    "description": "JSON Patch operations array (RFC 6902)",
                    "items": {"type": "object"},
                },
            },
            "required": ["fqn", "patch"],
        },
    },
    {
        "name": "read_yaml_file",
        "description": "Read a dbt YAML file from the project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path from project root, e.g. dbt/models/marts/_marts.yml",
                }
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_yaml_file",
        "description": (
            "Write updated content to a dbt YAML file. "
            "Only call this after the user has explicitly said 'confirm'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path from project root, e.g. dbt/models/marts/_marts.yml",
                },
                "content": {"type": "string", "description": "Full YAML content to write"},
            },
            "required": ["file_path", "content"],
        },
    },
]


def _execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "search_metadata":
            result = om_client.search_metadata(**inputs)
        elif name == "get_entity_details":
            result = om_client.get_entity_details(**inputs)
        elif name == "get_entity_lineage":
            result = om_client.get_entity_lineage(**inputs)
        elif name == "patch_entity":
            result = om_client.patch_entity(**inputs)
        elif name == "read_yaml_file":
            result = yaml_tools.read_yaml_file(**inputs)
            return result if isinstance(result, str) else json.dumps(result)
        elif name == "write_yaml_file":
            result = yaml_tools.write_yaml_file(**inputs)
        else:
            result = {"error": f"Unknown tool: {name}"}
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


class Agent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.conversations: dict[str, list] = {}

    def run(self, thread_ts: str, user_message: str) -> str:
        history = self.conversations.get(thread_ts, [])
        history.append({"role": "user", "content": user_message})

        for _ in range(10):  # max tool call rounds
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=history,
            )

            history.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                text = next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )
                self.conversations[thread_ts] = history
                return text

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = _execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                history.append({"role": "user", "content": tool_results})
                self.conversations[thread_ts] = history
                continue

            break

        self.conversations[thread_ts] = history
        return "Something went wrong — no response generated."

    def clear(self, thread_ts: str):
        self.conversations.pop(thread_ts, None)
