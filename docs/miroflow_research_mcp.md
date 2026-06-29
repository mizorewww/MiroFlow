# MiroFlow Research MCP

This MCP wrapper exposes MiroFlow as one fixed research tool.

The tool input is intentionally limited to:

- `question` (required): the research question.
- `context` (optional): background context for the question.

The caller cannot choose the MiroFlow agent config, output directory, task id,
or runtime settings. Those are controlled by environment variables.

## Tool

Server module:

```bash
python -m src.tool.mcp_servers.miroflow_research_mcp_server
```

Tool name:

```text
research
```

Arguments:

```json
{
  "question": "What is the current NASDAQ Composite index price and what are the main factors affecting it today?",
  "context": "Optional background context."
}
```

Return value:

```text
The generated Markdown report from logs/mcp/<task_id>.md
```

## Environment Configuration

Default config:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek
```

Useful env vars:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek
MIROFLOW_MCP_OUTPUT_DIR=logs/mcp
MIROFLOW_MCP_TIMEOUT=3600
MIROFLOW_MCP_LOGGER_LEVEL=ERROR
MIROFLOW_MCP_UV_CACHE_DIR=/private/tmp/miroflow-uv-cache
```

Normal provider credentials still come from `.env` or process env:

```bash
DEEPSEEK_API_KEY=...
SERPER_API_KEY=...
JINA_API_KEY=...
CODEX_HOME=.local/codex-home
```

## Using It Inside MiroFlow

Add the tool config to an agent:

```yaml
tool_config:
  - tool-miroflow-research
```

The config file is:

```text
config/tool/tool-miroflow-research.yaml
```

## Direct Smoke Test

You can list the MCP tool with:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek \
python -m src.tool.mcp_servers.miroflow_research_mcp_server
```

For real client usage, call `research` with only `question` and optional
`context`. The server generates an internal task id, runs:

```text
main.py trace --config_file_name=$MIROFLOW_MCP_CONFIG_NAME
```

then returns the Markdown report content.
