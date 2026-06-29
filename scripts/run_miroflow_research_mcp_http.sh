#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export MIROFLOW_MCP_CONFIG_NAME="${MIROFLOW_MCP_CONFIG_NAME:-agent_hybrid_codex_deepseek}"
export MIROFLOW_MCP_OUTPUT_DIR="${MIROFLOW_MCP_OUTPUT_DIR:-logs/mcp}"
export MIROFLOW_MCP_TIMEOUT="${MIROFLOW_MCP_TIMEOUT:-3600}"
export MIROFLOW_MCP_HOST="${MIROFLOW_MCP_HOST:-127.0.0.1}"
export MIROFLOW_MCP_PORT="${MIROFLOW_MCP_PORT:-8080}"
export MIROFLOW_MCP_PATH="${MIROFLOW_MCP_PATH:-/mcp}"

python -m src.tool.mcp_servers.miroflow_research_mcp_server \
  --transport http \
  --host "$MIROFLOW_MCP_HOST" \
  --port "$MIROFLOW_MCP_PORT" \
  --path "$MIROFLOW_MCP_PATH"
