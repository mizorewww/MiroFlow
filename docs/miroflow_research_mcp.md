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
MIROFLOW_MCP_SERVICE_LOG_DIR=logs/mcp_http_service
MIROFLOW_MCP_RESTART_DELAY=5
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

Each `research` call also stores task-level diagnostics next to the normal
Markdown and JSON trace:

```text
logs/mcp/<task_id>.md
logs/mcp/<task_id>.log
logs/mcp/<task_id>.stdout.log
logs/mcp/<task_id>.stderr.log
```

## HTTP / Streamable HTTP Server

Start the HTTP MCP server:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek \
MIROFLOW_MCP_HOST=0.0.0.0 \
MIROFLOW_MCP_PORT=8080 \
MIROFLOW_MCP_PATH=/mcp \
uv run ./scripts/run_miroflow_research_mcp_http.sh
```

For long-running service deployments, use the supervised runner instead:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek \
MIROFLOW_MCP_HOST=0.0.0.0 \
MIROFLOW_MCP_PORT=8080 \
MIROFLOW_MCP_PATH=/mcp \
MIROFLOW_MCP_SERVICE_LOG_DIR=logs/mcp_http_service \
uv run ./scripts/run_miroflow_research_mcp_http_supervised.sh
```

The supervised runner restarts the MCP HTTP server after unexpected exits and
keeps one stdout/stderr pair for each server run:

```text
logs/mcp_http_service/supervisor.log
logs/mcp_http_service/current.stdout.log
logs/mcp_http_service/current.stderr.log
logs/mcp_http_service/server_<timestamp>_<pid>.stdout.log
logs/mcp_http_service/server_<timestamp>_<pid>.stderr.log
```

If a client reports `MCP error -32000: Connection closed`, check the service
supervisor log first, then inspect the task-level stdout/stderr files for the
request that was running at the time.

The endpoint is:

```text
http://<host>:8080/mcp
```

For a local-only server, keep `MIROFLOW_MCP_HOST=127.0.0.1`. For LAN access,
use `0.0.0.0`.

Example Python client:

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client("http://127.0.0.1:8080/mcp") as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "research",
                arguments={"question": "Say exactly: HTTP_OK"},
            )
            print(result.content[-1].text)


asyncio.run(main())
```

If the server machine does not have Codex CLI installed and logged in, set
`MIROFLOW_MCP_CONFIG_NAME=agent_llm_deepseek` for smoke tests. The hybrid config
requires the server's Codex account to be available.
