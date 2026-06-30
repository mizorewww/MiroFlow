#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")/.."

export MIROFLOW_MCP_CONFIG_NAME="${MIROFLOW_MCP_CONFIG_NAME:-agent_hybrid_codex_deepseek}"
export MIROFLOW_MCP_OUTPUT_DIR="${MIROFLOW_MCP_OUTPUT_DIR:-logs/mcp}"
export MIROFLOW_MCP_TIMEOUT="${MIROFLOW_MCP_TIMEOUT:-3600}"
export MIROFLOW_MCP_HOST="${MIROFLOW_MCP_HOST:-127.0.0.1}"
export MIROFLOW_MCP_PORT="${MIROFLOW_MCP_PORT:-8080}"
export MIROFLOW_MCP_PATH="${MIROFLOW_MCP_PATH:-/mcp}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

log_dir="${MIROFLOW_MCP_SERVICE_LOG_DIR:-logs/mcp_http_service}"
restart_delay="${MIROFLOW_MCP_RESTART_DELAY:-5}"
restart_limit="${MIROFLOW_MCP_RESTART_LIMIT:-0}"

mkdir -p "$log_dir"

supervisor_log="$log_dir/supervisor.log"
child_pid=""
stop_requested=0
restart_count=0

timestamp() {
  date "+%Y-%m-%dT%H:%M:%S%z"
}

log_supervisor() {
  printf "[%s] %s\n" "$(timestamp)" "$*" | tee -a "$supervisor_log" >&2
}

shutdown() {
  stop_requested=1
  log_supervisor "shutdown requested"
  if [[ -n "${child_pid:-}" ]] && kill -0 "$child_pid" 2>/dev/null; then
    kill "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit 0
}

trap shutdown INT TERM

log_supervisor "supervisor started; config=$MIROFLOW_MCP_CONFIG_NAME host=$MIROFLOW_MCP_HOST port=$MIROFLOW_MCP_PORT path=$MIROFLOW_MCP_PATH"

while true; do
  run_id="$(date "+%Y%m%d_%H%M%S")_$$"
  stdout_log="$log_dir/server_${run_id}.stdout.log"
  stderr_log="$log_dir/server_${run_id}.stderr.log"

  ln -sfn "$(basename "$stdout_log")" "$log_dir/current.stdout.log"
  ln -sfn "$(basename "$stderr_log")" "$log_dir/current.stderr.log"

  log_supervisor "starting MCP server run_id=$run_id"
  python -m src.tool.mcp_servers.miroflow_research_mcp_server \
    --transport http \
    --host "$MIROFLOW_MCP_HOST" \
    --port "$MIROFLOW_MCP_PORT" \
    --path "$MIROFLOW_MCP_PATH" \
    >>"$stdout_log" 2>>"$stderr_log" &

  child_pid=$!
  wait "$child_pid"
  exit_code=$?
  child_pid=""

  if [[ "$stop_requested" == "1" ]]; then
    log_supervisor "server stopped because shutdown was requested; exit_code=$exit_code"
    exit 0
  fi

  restart_count=$((restart_count + 1))
  log_supervisor "server exited unexpectedly; exit_code=$exit_code restart_count=$restart_count stdout=$stdout_log stderr=$stderr_log"

  if [[ "$restart_limit" != "0" && "$restart_count" -ge "$restart_limit" ]]; then
    log_supervisor "restart limit reached; exiting supervisor"
    exit "$exit_code"
  fi

  log_supervisor "restarting after ${restart_delay}s"
  sleep "$restart_delay"
done
