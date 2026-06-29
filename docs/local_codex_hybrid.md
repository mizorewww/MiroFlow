# Local Codex Hybrid Provider

This fork adds a local Codex CLI provider so MiroFlow can use the Codex account
already logged in on this Mac, while keeping faster API models such as DeepSeek
on worker duties.

## Repository Setup

- Baseline local changes were committed before this work as
  `0c51504 feat: configure deepseek and live tracing`.
- `origin` now points to `git@github.com:mizorewww/MiroFlow.git`.
- Local `main` tracks `origin/main`, so plain `git push` pushes to the fork.
- The original project remote is kept as `upstream`:
  `git@github.com:MiroMindAI/MiroFlow.git`.

## Credentials

- DeepSeek, Serper, and Jina keys stay in `.env`, which is ignored by Git.
- Codex authentication stays in the local Codex home directory.
- For this Mac, `.local/codex-home` is a symlink to the local Codex config
  directory. `.local/` is ignored, so neither the symlink nor auth files are
  committed.

## Codex Provider

`src/llm/providers/codex_cli_client.py` defines `CodexCliClient`.

The provider does not read Codex tokens. For each MiroFlow LLM turn it invokes:

```bash
codex --ask-for-approval never exec --ephemeral --sandbox read-only \
  --cd . -m gpt-5.5 -c 'model_reasoning_effort="xhigh"'
```

The prompt is passed through standard input, and the final Codex assistant
message is read from a temporary output file. XML-style MiroFlow tool calls are
still parsed by the existing tool-call parser.

Useful overrides:

- `CODEX_COMMAND`: Codex binary path, default `codex`
- `CODEX_HOME`: Codex home, default `.local/codex-home`
- `CODEX_WORKDIR`: working directory passed to Codex, default `.`
- `CODEX_SANDBOX`: Codex sandbox, default `read-only`
- `CODEX_APPROVAL_POLICY`: Codex approval policy, default `never`
- `CODEX_TIMEOUT`: per-turn timeout in seconds, default `1800`
- `codex_search`: config flag that adds Codex CLI `--search`, enabling native
  Responses `web_search` for that Codex turn

## Recommended Agent Split

Use `config/agent_hybrid_codex_deepseek.yaml` for hybrid runs.

- Main agent: `CodexCliClient`, `gpt-5.5`, `xhigh`
  - Role: instruction following, delegation, synthesis, final report.
  - Tool access: `agent-worker` and `agent-codex-search`.
- `agent-worker`: `DeepSeekOpenRouterClient`, `deepseek-v4-pro`
  - Role: fast Serper/Jina web research and page reading.
  - Tools: `tool-reading`, `tool-searching`.
- `agent-codex-search`: `CodexCliClient`, `gpt-5.5`, `xhigh`, `codex_search: true`
  - Role: independent web research through Codex native `web_search`.
  - Tools: no MiroFlow MCP tools; Codex performs native web searches internally.

This keeps slow high-quality reasoning out of repeated web-search loops and
uses DeepSeek for latency-sensitive search/read work. When source quality or
search disagreement matters, the main agent can call both research components
and synthesize the stronger evidence.

## Markdown Export

`utils/trace_single_task.py` now writes a stable Markdown report after every
`trace` run:

```text
logs/<task_id>.md
```

The report contains metadata, task text, extracted boxed answer, and final
summary. The existing JSON trace remains at:

```text
logs/<task_id>.log
```

## Run Examples

Pure DeepSeek:

```bash
uv run python main.py trace \
  --config_file_name=agent_llm_deepseek \
  --task_id=deepseek_nasdaq \
  --task="What is the current NASDAQ Composite index price and what are the main factors affecting it today? Use current web sources and answer briefly."
```

Hybrid Codex + DeepSeek:

```bash
uv run python main.py trace \
  --config_file_name=agent_hybrid_codex_deepseek \
  --task_id=hybrid_nasdaq \
  --task="What is the current NASDAQ Composite index price and what are the main factors affecting it today?"
```

## Codex Account Smoke Test

On this machine, Codex CLI was available and logged in via ChatGPT. A direct
three-run smoke test with `gpt-5.5` and `model_reasoning_effort="xhigh"`
returned `CODEX_OK_1`, `CODEX_OK_2`, and `CODEX_OK_3`.
