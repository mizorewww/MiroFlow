# MiroFlow 远端部署与运维技术报告

## 1. 概述

本文记录当前 MiroFlow fork 在服务器 Mac 上的部署方式、服务架构、反向代理配置、启动管理方式、更新流程和常见排障命令。

服务器信息：

```text
服务器地址: 192.168.31.134
主机名: MacBook-Pro-M2.local
用户: aac6fef
项目目录: /Users/aac6fef/Developers/MiroFlow
```

当前对外暴露的 MCP HTTP 地址：

```text
http://192.168.31.134:8080/mcp/mirrorflow/mcp
```

该 MCP 只暴露一个工具：

```text
research(question, context="")
```

调用方只能传：

- `question`：必填，研究问题
- `context`：可选，上下文

调用方不能传配置名、任务 ID、输出目录等运行参数。MiroFlow 使用哪个 Agent 配置，由服务器环境变量固定控制。

## 2. 总体架构

当前链路如下：

```text
MCP Client
  -> http://192.168.31.134:8080/mcp/mirrorflow/mcp
  -> Caddy, 由 Homebrew service 管理
  -> 反向代理到 127.0.0.1:8766/mcp/
  -> MiroFlow MCP HTTP Server, 由 Homebrew service 管理
  -> main.py trace
  -> logs/mcp_http_hybrid/<task_id>.md
```

服务监听关系：

```text
Caddy 对外监听: 0.0.0.0:8080
MiroFlow MCP 内部监听: 127.0.0.1:8766
```

这样做的好处是：

- Caddy 负责对外入口和路径管理。
- MiroFlow 只监听本机地址，减少暴露面。
- 两个服务都交给 Homebrew service 管理，重启和开机自启逻辑统一。

## 3. 项目部署方式

项目从本地开发机打包后传到服务器，再解压到：

```text
/Users/aac6fef/Developers/MiroFlow
```

部署包排除了这些临时或大型目录：

```text
.git
.venv
logs
__pycache__
.local
```

服务器上的项目目录包含：

```text
.env
.python-version
config/
docs/
main.py
scripts/
src/
uv.lock
```

项目固定使用 Python 3.13：

```text
.python-version = 3.13
```

固定 Python 3.13 的原因是 Python 3.14 下部分依赖尚无可用 wheel，例如 `onnxruntime`。如果让 `uv` 自动选择 Python 3.14，会导致依赖同步失败。

依赖安装命令：

```bash
cd /Users/aac6fef/Developers/MiroFlow
UV_CACHE_DIR=/tmp/miroflow-uv-cache uv sync
```

Codex 配置目录软链接：

```text
/Users/aac6fef/Developers/MiroFlow/.local/codex-home -> /Users/aac6fef/.codex
```

远端 Codex CLI：

```text
/opt/homebrew/bin/codex
```

Codex 验证命令：

```bash
codex --version
codex login status
```

当前已验证远端 Codex 登录状态为：

```text
Logged in using ChatGPT
```

## 4. MiroFlow MCP 服务

MiroFlow MCP HTTP 服务入口脚本：

```text
scripts/run_miroflow_research_mcp_http.sh
```

Homebrew service 使用带自动重启的 supervisor 入口：

```text
scripts/run_miroflow_research_mcp_http_supervised.sh
```

脚本实际启动：

```bash
python -m src.tool.mcp_servers.miroflow_research_mcp_server \
  --transport http \
  --host "$MIROFLOW_MCP_HOST" \
  --port "$MIROFLOW_MCP_PORT" \
  --path "$MIROFLOW_MCP_PATH"
```

MCP Server 模块：

```text
src/tool/mcp_servers/miroflow_research_mcp_server.py
```

MCP 工具配置：

```text
config/tool/tool-miroflow-research.yaml
```

MCP 工具行为：

1. 接收 `question` 和可选 `context`。
2. 如果已有 `research` 任务正在运行，先终止旧任务的整个进程组，并为旧任务写入 superseded Markdown 报告。
3. 生成新的内部 task id。
4. 调用 `main.py trace`。
5. 使用固定配置运行 MiroFlow Agent。
6. 读取生成的 Markdown 报告。
7. 将完整 Markdown 内容返回给 MCP 调用方。
8. 同时保留本次任务的 JSON trace、Markdown、stdout 和 stderr 诊断日志。

当前 HTTP MCP 服务是抢占式单任务模型：同一时间只允许一个 `research` 任务运行。新请求会立即取代旧请求，而不是排队等待。这是为了避免客户端连接断开或自动重试时堆出多个长任务。

当前固定 Agent 配置：

```text
agent_hybrid_codex_deepseek
```

也就是说，当前 MCP 后端使用：

- Codex/GPT 5.5 xhigh 作为主控和高质量综合器。
- DeepSeek V4 Pro 作为快速 worker。
- Codex 原生 `web_search` 作为可选搜索组件。

## 5. MiroFlow 的 Homebrew Service

为了用 `brew services` 管理 MiroFlow，服务器上创建了一个本地 Homebrew formula：

```text
/opt/homebrew/Library/Taps/local/homebrew-miroflow/Formula/miroflow-mcp.rb
```

该 formula 的 service 环境变量如下：

```bash
MIROFLOW_MCP_CONFIG_NAME=agent_hybrid_codex_deepseek
MIROFLOW_MCP_OUTPUT_DIR=logs/mcp_http_hybrid
MIROFLOW_MCP_TIMEOUT=3600
MIROFLOW_MCP_HOST=127.0.0.1
MIROFLOW_MCP_PORT=8766
MIROFLOW_MCP_PATH=/mcp
MIROFLOW_MCP_SERVICE_LOG_DIR=logs/mcp_http_service
MIROFLOW_MCP_RESTART_DELAY=5
CODEX_SKIP_GIT_REPO_CHECK=true
LOGGER_LEVEL=ERROR
UV_CACHE_DIR=/tmp/miroflow-uv-cache
```

说明：

- `MIROFLOW_MCP_CONFIG_NAME` 决定 MCP 后端使用哪个 MiroFlow 配置。
- `MIROFLOW_MCP_HOST=127.0.0.1` 表示 MiroFlow 不直接对外暴露。
- `MIROFLOW_MCP_PORT=8766` 是内部 MCP HTTP 端口。
- `MIROFLOW_MCP_SERVICE_LOG_DIR` 是 supervisor 和 MCP server 进程日志目录。
- `MIROFLOW_MCP_RESTART_DELAY` 是 MCP server 子进程异常退出后的重启等待秒数。
- `CODEX_SKIP_GIT_REPO_CHECK=true` 是打包部署场景的必要项。因为远端部署包不一定包含 `.git` 目录，Codex 默认会拒绝在未信任目录运行。

Homebrew/launchd 层日志：

```text
/tmp/miroflow_mcp_http.homebrew.log
/tmp/miroflow_mcp_http.homebrew.err.log
```

MiroFlow supervisor 层日志：

```text
/Users/aac6fef/Developers/MiroFlow/logs/mcp_http_service/supervisor.log
/Users/aac6fef/Developers/MiroFlow/logs/mcp_http_service/current.stdout.log
/Users/aac6fef/Developers/MiroFlow/logs/mcp_http_service/current.stderr.log
```

每次 MCP server 子进程启动都会生成一组按时间命名的日志：

```text
logs/mcp_http_service/server_<timestamp>_<pid>.stdout.log
logs/mcp_http_service/server_<timestamp>_<pid>.stderr.log
```

每次 `research` 调用还会保存任务级诊断日志：

```text
logs/mcp_http_hybrid/<task_id>.md
logs/mcp_http_hybrid/<task_id>.log
logs/mcp_http_hybrid/<task_id>.stdout.log
logs/mcp_http_hybrid/<task_id>.stderr.log
```

## 6. Caddy 反向代理

Caddy 由 Homebrew 安装并用 Homebrew service 管理。

Caddyfile 路径：

```text
/opt/homebrew/etc/Caddyfile
```

当前配置：

```caddyfile
{
    auto_https off
}

:8080 {
    handle /mcp/mirrorflow/mcp {
        rewrite * /mcp/
        reverse_proxy 127.0.0.1:8766
    }

    handle /mcp/mirrorflow/mcp/* {
        uri strip_prefix /mcp/mirrorflow
        reverse_proxy 127.0.0.1:8766
    }

    respond "MiroFlow MCP endpoint: /mcp/mirrorflow/mcp" 200
}
```

外部路径：

```text
/mcp/mirrorflow/mcp
```

内部 FastMCP 路径：

```text
/mcp/
```

因此 Caddy 做了两件事：

1. 把外部路径 `/mcp/mirrorflow/mcp` 改写为内部路径 `/mcp/`。
2. 将请求转发到 `127.0.0.1:8766`。

当前对外访问地址：

```text
http://192.168.31.134:8080/mcp/mirrorflow/mcp
```

## 7. 服务管理命令

查看所有 Homebrew services：

```bash
brew services list
```

启动服务：

```bash
brew services start local/miroflow/miroflow-mcp
brew services start caddy
```

重启服务：

```bash
brew services restart local/miroflow/miroflow-mcp
brew services restart caddy
```

停止服务：

```bash
brew services stop local/miroflow/miroflow-mcp
brew services stop caddy
```

查看服务详情：

```bash
brew services info miroflow-mcp
brew services info caddy
```

当前期望状态：

```text
caddy        started
miroflow-mcp started
```

当前期望监听：

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

期望结果：

```text
caddy       *:8080
python3.13  127.0.0.1:8766
```

## 8. 调用验证

可以从客户端用 MCP streamable HTTP client 验证：

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    url = "http://192.168.31.134:8080/mcp/mirrorflow/mcp"
    async with streamablehttp_client(url, timeout=30, sse_read_timeout=480) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])
            result = await session.call_tool(
                "research",
                arguments={"question": "Say exactly: CADDY_MCP_OK"},
            )
            print(result.content[-1].text)


asyncio.run(main())
```

期望工具列表：

```text
['research']
```

已完成的 smoke test 返回了 Markdown 报告，最终答案为：

```text
CADDY_MCP_OK
```

报告输出目录：

```text
/Users/aac6fef/Developers/MiroFlow/logs/mcp_http_hybrid/
```

## 9. 更新部署流程

推荐更新方式如下。

本地开发机：

```bash
cd /Users/aac6fef/Developer/MiroFlow
git status --short
git push
```

打包：

```bash
tar \
  --exclude='./.git' \
  --exclude='./.venv' \
  --exclude='./logs' \
  --exclude='./__pycache__' \
  --exclude='*/__pycache__' \
  --exclude='./.local' \
  -czf /tmp/miroflow-deploy.tgz .
```

上传：

```bash
scp /tmp/miroflow-deploy.tgz 192.168.31.134:/tmp/miroflow-deploy.tgz
```

服务器上更新：

```bash
ssh 192.168.31.134
cd /Users/aac6fef/Developers
mv MiroFlow "MiroFlow.backup.$(date +%Y%m%d%H%M%S)"
mkdir MiroFlow
tar -xzf /tmp/miroflow-deploy.tgz -C MiroFlow
cd MiroFlow
mkdir -p .local
ln -sfn /Users/aac6fef/.codex .local/codex-home
UV_CACHE_DIR=/tmp/miroflow-uv-cache uv sync
brew services restart local/miroflow/miroflow-mcp
brew services restart caddy
```

如果只是小范围代码改动，也可以只复制相关文件到服务器，然后重启：

```bash
brew services restart local/miroflow/miroflow-mcp
```

## 10. 修改 Agent 配置

当前配置写在 Homebrew formula 中：

```text
/opt/homebrew/Library/Taps/local/homebrew-miroflow/Formula/miroflow-mcp.rb
```

当前值：

```text
MIROFLOW_MCP_CONFIG_NAME: "agent_hybrid_codex_deepseek"
```

如果要切换成纯 DeepSeek：

```text
MIROFLOW_MCP_CONFIG_NAME: "agent_llm_deepseek"
```

修改后需要：

```bash
brew reinstall local/miroflow/miroflow-mcp
brew services restart local/miroflow/miroflow-mcp
```

## 11. 常见排障

查看服务：

```bash
brew services list
brew services info miroflow-mcp
brew services info caddy
```

查看 MiroFlow 日志：

```bash
tail -n 100 /tmp/miroflow_mcp_http.homebrew.err.log
tail -n 100 /tmp/miroflow_mcp_http.homebrew.log
tail -n 100 /Users/aac6fef/Developers/MiroFlow/logs/mcp_http_service/supervisor.log
tail -n 100 /Users/aac6fef/Developers/MiroFlow/logs/mcp_http_service/current.stderr.log
```

查看端口：

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:8766 -sTCP:LISTEN
```

验证 Caddy 配置：

```bash
caddy validate --config /opt/homebrew/etc/Caddyfile
brew services restart caddy
```

验证 Codex：

```bash
codex --version
codex login status
```

Codex 直连 smoke test：

```bash
cd /Users/aac6fef/Developers/MiroFlow
printf "Say exactly: CODEX_REMOTE_OK" | \
  codex --ask-for-approval never exec \
    --skip-git-repo-check \
    --ephemeral \
    --sandbox read-only \
    --cd . \
    -m gpt-5.5 \
    -c 'model_reasoning_effort="xhigh"' \
    -
```

MiroFlow 内部 MCP endpoint 测试：

```bash
curl -i http://127.0.0.1:8766/mcp/
```

Caddy 外部路径测试：

```bash
curl -i http://127.0.0.1:8080/mcp/mirrorflow/mcp
```

常见问题：

- `MCP error -32000: Connection closed`：先确认 service 是否已被拉起：`brew services info miroflow-mcp`。再查看 `logs/mcp_http_service/supervisor.log` 是否出现 `server exited unexpectedly`，并查看对应的 `server_<timestamp>_<pid>.stderr.log`。如果是某次任务导致连接断开，继续看 `logs/mcp_http_hybrid/<task_id>.stdout.log` 和 `.stderr.log`。
- `Not inside a trusted directory`：确认 `CODEX_SKIP_GIT_REPO_CHECK=true`。
- `address already in use`：说明端口已有旧进程，先停掉旧服务或检查 `lsof`。
- `onnxruntime` 安装失败：确认 `.python-version` 是 `3.13`，删除 `.venv` 后重新 `uv sync --python 3.13`。
- Caddy 路径异常：检查 `/mcp/mirrorflow/mcp` 是否被改写到 `/mcp/`。
- MCP 工具列表为空：先直连 `127.0.0.1:8766/mcp/`，再检查 Caddy 反代。
