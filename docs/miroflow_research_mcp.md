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

## HTTP / Streamable HTTP Server

Start the HTTP MCP server:

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek \
MIROFLOW_MCP_HOST=0.0.0.0 \
MIROFLOW_MCP_PORT=8080 \
MIROFLOW_MCP_PATH=/mcp \
uv run ./scripts/run_miroflow_research_mcp_http.sh
```

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
