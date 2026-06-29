# MiroFlow CLI Usage Guide

这份指南说明如何从命令行调用当前 fork 里的主要能力，包括纯 DeepSeek、Codex + DeepSeek 混合、Codex 原生 web_search 子代理、实时日志和 Markdown 导出。

## 0. 前置条件

在项目根目录运行：

```bash
cd /Users/aac6fef/Developer/MiroFlow
```

确认本地依赖可用：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache uv run python main.py print-config --config_file_name=agent_hybrid_codex_deepseek
```

需要的本地凭据：

- `.env`：保存 `DEEPSEEK_API_KEY`、`SERPER_API_KEY`、`JINA_API_KEY` 等。
- `.local/codex-home`：本机 Codex 配置目录的 symlink，已被 `.gitignore` 忽略。
- Codex 登录：可用 `codex login status` 检查。

## 1. 最常用命令：跑单个任务

基本格式：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=<配置名> \
  --task_id=<任务ID> \
  --task="<任务描述>"
```

每次 `trace` 跑完会生成：

- `logs/<task_id>.md`：稳定 Markdown 报告，适合阅读和归档。
- `logs/<task_id>.log`：完整 JSON trace，适合调试。

## 2. 纯 DeepSeek：快、便宜、适合常规搜索

使用配置：`agent_llm_deepseek`

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_llm_deepseek \
  --task_id=deepseek_example \
  --task="What is the current NASDAQ Composite index price and what are the main factors affecting it today? Use current web sources and answer briefly with sources."
```

这个配置会让 DeepSeek 主代理直接使用 Serper/Jina 搜索和网页读取工具。

适合：

- 大量普通网页搜索。
- 对速度敏感的研究任务。
- 成本优先的批量任务。

## 3. 混合模式：Codex 主控 + DeepSeek/Codex 搜索组件

使用配置：`agent_hybrid_codex_deepseek`

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=hybrid_example \
  --task="Use the available research agents to answer: What is the current NASDAQ Composite index price and what are the main factors affecting it today? Compare evidence and answer briefly with sources."
```

这个配置里主控是 Codex/GPT 5.5 xhigh。它能调用两个研究组件：

- `agent-worker`：DeepSeek + Serper/Jina，适合快速搜索、网页抓取、读取页面。
- `agent-codex-search`：Codex/GPT 5.5 + 原生 `web_search`，适合独立交叉验证、官方来源优先、复杂来源判断。

## 4. 指定使用某个搜索组件

MiroFlow 的主控会读任务描述。想强制某个组件时，直接在 `--task` 里写清楚。

只用 DeepSeek 搜索组件：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=use_deepseek_worker \
  --task="Use agent-worker to collect current web evidence. Then summarize the answer with sources: What is the current NASDAQ Composite index price?"
```

只用 Codex 原生 web_search：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=use_codex_search \
  --task="Use agent-codex-search to collect current web evidence from official sources only. What is the latest headline on OpenAI's official news page? Return title and source URL."
```

两个都用，并让主控合并：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=compare_two_searches \
  --task="Use both agent-worker and agent-codex-search to independently research this question. Compare conflicts, choose the stronger evidence, and write one merged answer with sources: What is the current NASDAQ Composite index price and what are the main factors affecting it today?"
```

## 5. 开启实时日志

实时输出 LLM 可见回答、工具调用、工具结果，以及 DeepSeek 暴露的 reasoning 内容：

```bash
MIROFLOW_LIVE_TRACE=1 \
MIROFLOW_LIVE_TRACE_MAX_CHARS=1600 \
LOGGER_LEVEL=INFO \
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=live_trace_example \
  --task="Use both research agents to compare the latest OpenAI news item and summarize the result."
```

注意：

- DeepSeek 如果返回 reasoning，会在实时日志里显示。
- Codex/GPT 的隐藏 CoT 不会被导出；能看到的是它的可见行为、工具调用和最终回答。

## 6. 常用 Hydra 覆盖参数

命令最后可以追加配置覆盖项。

限制主控回合数：

```bash
main_agent.max_turns=3
```

限制 DeepSeek worker 回合数：

```bash
sub_agents.agent-worker.max_turns=3
```

限制 Codex web_search 子代理回合数：

```bash
sub_agents.agent-codex-search.max_turns=1
```

改输出目录：

```bash
output_dir=logs/my_run
```

完整例子：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=bounded_run \
  --task="Use both search agents and answer briefly: What changed in OpenAI news recently?" \
  main_agent.max_turns=4 \
  sub_agents.agent-worker.max_turns=3 \
  sub_agents.agent-codex-search.max_turns=1 \
  output_dir=logs/bounded_run
```

## 7. 带文件任务

使用 `--task_file_name`：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_quickstart_reading \
  --task_id=read_xlsx \
  --task="What is the first country listed in the XLSX file that has a name starting with Co?" \
  --task_file_name="data/FSI-2023-DOWNLOAD.xlsx"
```

## 8. 查看配置

打印当前默认配置：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py print-config
```

打印指定配置：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py print-config --config_file_name=agent_hybrid_codex_deepseek
```

如果想看完整运行时配置 dump：

```bash
MIROFLOW_PRINT_CONFIG=1 \
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=config_debug \
  --task="Say hello."
```

## 9. 跑 benchmark

基本格式：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py common-benchmark \
  --config_file_name=<配置名> \
  output_dir="logs/<run_name>"
```

例子：

```bash
UV_CACHE_DIR=/private/tmp/miroflow-uv-cache \
uv run python main.py common-benchmark \
  --config_file_name=agent_hybrid_codex_deepseek \
  output_dir="logs/hybrid_benchmark_test"
```

限制任务数量：

```bash
benchmark.execution.max_tasks=10
```

限制并发：

```bash
benchmark.execution.max_concurrent=2
```

## 10. 评分和汇总

已有 CLI 子命令：

```bash
uv run python main.py eval-answer
uv run python main.py avg-score
uv run python main.py score-from-log
uv run python main.py prepare-benchmark
```

这些命令主要服务 benchmark/eval 流程。具体参数依赖对应 benchmark 数据和日志结构，日常单任务调试优先使用 `trace`。

## 11. 推荐工作流

日常问答/搜索：

```bash
uv run python main.py trace --config_file_name=agent_llm_deepseek --task_id=quick --task="..."
```

需要高质量最终回答：

```bash
uv run python main.py trace --config_file_name=agent_hybrid_codex_deepseek --task_id=hybrid --task="..."
```

需要双搜索交叉验证：

```bash
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=cross_check \
  --task="Use both agent-worker and agent-codex-search, compare evidence, then write the merged answer: ..."
```

看结果：

```bash
open logs/<task_id>.md
```

调试完整过程：

```bash
less logs/<task_id>.log
```

