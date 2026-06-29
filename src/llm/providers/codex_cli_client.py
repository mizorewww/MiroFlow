# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import dataclasses
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from omegaconf import DictConfig
from tenacity import retry, stop_after_attempt, wait_exponential

from src.llm.provider_client_base import LLMProviderClientBase
from src.logging.live_trace import redact_secrets
from src.logging.logger import bootstrap_logger

LOGGER_LEVEL = os.getenv("LOGGER_LEVEL", "INFO")
logger = bootstrap_logger(level=LOGGER_LEVEL)


class CodexCliError(Exception):
    pass


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower().strip() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclasses.dataclass
class CodexCliClient(LLMProviderClientBase):
    """LLM provider that delegates each turn to the local Codex CLI.

    This provider intentionally does not read Codex tokens itself. It invokes the
    official `codex exec` command, which uses the user's configured CODEX_HOME.
    """

    def _create_client(self, config: DictConfig):
        return None

    def __post_init__(self):
        super().__post_init__()
        self.codex_command = self.cfg.llm.get("codex_command", "codex")
        self.codex_home = self.cfg.llm.get("codex_home", "")
        self.codex_sandbox = self.cfg.llm.get("codex_sandbox", "read-only")
        self.codex_approval_policy = self.cfg.llm.get("codex_approval_policy", "never")
        self.codex_timeout = int(self.cfg.llm.get("codex_timeout", 1800))
        self.codex_workdir = self.cfg.llm.get("codex_workdir", os.getcwd())
        self.codex_ephemeral = _as_bool(self.cfg.llm.get("codex_ephemeral", True))
        self.codex_json_events = _as_bool(self.cfg.llm.get("codex_json_events", False))
        self.codex_search = _as_bool(self.cfg.llm.get("codex_search", False))

    def _content_to_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        return str(content)

    def _format_message_history(self, messages: List[Dict[str, Any]]) -> str:
        lines = []
        for index, message in enumerate(messages, 1):
            role = message.get("role", "unknown")
            content = self._content_to_text(message.get("content"))
            if message.get("tool_calls"):
                content += f"\n\nTool calls requested: {message['tool_calls']}"
            lines.append(f"## Message {index}: {role}\n{content}".strip())
        return "\n\n".join(lines)

    def _build_codex_prompt(
        self, system_prompt: str, messages: List[Dict[str, Any]]
    ) -> str:
        conversation = self._format_message_history(messages)
        native_search_rule = (
            "- Codex native web_search is enabled. Use it internally when current web evidence is needed; do not emit a MiroFlow XML tool call for native web_search."
            if self.codex_search
            else "- Codex native web_search is disabled for this turn."
        )
        return f"""You are acting as the next assistant turn inside the MiroFlow agent runtime.

Important runtime rules:
- Return only the assistant message for this next turn.
- Do not inspect or edit local files unless the MiroFlow prompt explicitly asks you to call a tool.
- If you need a MiroFlow tool, output exactly one `<use_mcp_tool>...</use_mcp_tool>` block that follows the system prompt format, then stop.
- If no tool is needed, answer directly.
{native_search_rule}

# MiroFlow System Prompt
{system_prompt}

# Conversation So Far
{conversation}

# Your Next Assistant Message
"""

    @retry(wait=wait_exponential(multiplier=2), stop=stop_after_attempt(2))
    async def _create_message(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools_definitions,
        keep_tool_result: int = -1,
    ):
        filtered_messages = self._remove_tool_result_from_messages(
            messages, keep_tool_result
        )
        prompt = self._build_codex_prompt(system_prompt, filtered_messages)

        output_file = tempfile.NamedTemporaryFile(
            prefix="miroflow-codex-", suffix=".txt", delete=False
        )
        output_path = Path(output_file.name)
        output_file.close()
        cmd = [self.codex_command]
        if self.codex_search:
            cmd.append("--search")
        cmd.extend(
            [
                "--ask-for-approval",
                self.codex_approval_policy,
                "exec",
            ]
        )
        if self.codex_json_events:
            cmd.append("--json")
        if self.codex_ephemeral:
            cmd.append("--ephemeral")
        cmd.extend(
            [
                "--sandbox",
                self.codex_sandbox,
                "--cd",
                self.codex_workdir,
                "-m",
                self.model_name,
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "-o",
                str(output_path),
                "-",
            ]
        )
        cmd = [
            str(part) for part in cmd
        ]

        env = os.environ.copy()
        if self.codex_home:
            codex_home = Path(self.codex_home).expanduser()
            env["CODEX_HOME"] = str(
                codex_home if codex_home.is_absolute() else codex_home.resolve()
            )

        logger.debug("Calling Codex CLI provider")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(prompt.encode("utf-8")), timeout=self.codex_timeout
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.wait()
            raise CodexCliError(
                f"Codex CLI timed out after {self.codex_timeout} seconds"
            ) from exc

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise CodexCliError(
                "Codex CLI failed with exit code "
                f"{process.returncode}: {redact_secrets(stderr_text[-2000:])}"
            )

        assistant_text = ""
        if output_path.exists():
            assistant_text = output_path.read_text(encoding="utf-8").strip()
            try:
                output_path.unlink()
            except OSError:
                pass
        if not assistant_text:
            assistant_text = stdout_text.strip()
        if not assistant_text:
            raise CodexCliError(
                "Codex CLI returned no assistant message. "
                f"stderr={redact_secrets(stderr_text[-2000:])}"
            )

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(
                        role="assistant",
                        content=assistant_text,
                        tool_calls=None,
                        model_extra={},
                    ),
                )
            ],
            usage=None,
            provider_metadata={
                "stdout_tail": redact_secrets(stdout_text[-1000:]),
                "stderr_tail": redact_secrets(stderr_text[-1000:]),
            },
        )

    def process_llm_response(
        self, llm_response, message_history, agent_type="main"
    ) -> tuple[str, bool]:
        if not llm_response or not llm_response.choices:
            logger.error("Codex CLI did not return a valid response.")
            return "", True

        assistant_response_text = llm_response.choices[0].message.content or ""
        message_history.append({"role": "assistant", "content": assistant_response_text})
        logger.debug(f"Codex CLI Response: {assistant_response_text}")
        return assistant_response_text, False

    def extract_tool_calls_info(self, llm_response, assistant_response_text):
        from src.utils.parsing_utils import parse_llm_response_for_tool_calls

        return parse_llm_response_for_tool_calls(assistant_response_text)

    def update_message_history(
        self, message_history, tool_call_info, tool_calls_exceeded=False
    ):
        tool_call_info = [item for item in tool_call_info if item[1]["type"] == "text"]
        valid_tool_calls = [
            (tool_id, content)
            for tool_id, content in tool_call_info
            if tool_id != "FAILED"
        ]
        bad_tool_calls = [
            (tool_id, content)
            for tool_id, content in tool_call_info
            if tool_id == "FAILED"
        ]

        output_parts = []
        if tool_calls_exceeded:
            output_parts.append(
                f"You made too many tool calls. I processed {len(valid_tool_calls)} valid tool calls."
            )
        for i, (tool_id, content) in enumerate(valid_tool_calls, 1):
            output_parts.append(f"Valid tool call {i} result:\n{content['text']}")
        for i, (tool_id, content) in enumerate(bad_tool_calls, 1):
            output_parts.append(f"Failed tool call {i} result:\n{content['text']}")

        message_history.append(
            {
                "role": "user",
                "content": [{"type": "text", "text": "\n\n".join(output_parts)}],
            }
        )
        return message_history

    def parse_llm_response(self, llm_response) -> str:
        if not llm_response or not llm_response.choices:
            raise ValueError("Codex CLI did not return a valid response.")
        return llm_response.choices[0].message.content

    def handle_max_turns_reached_summary_prompt(self, message_history, summary_prompt):
        if message_history and message_history[-1]["role"] == "user":
            last_user_message = message_history.pop()
            return (
                self._content_to_text(last_user_message.get("content"))
                + "\n\n-----------------\n\n"
                + summary_prompt
            )
        return summary_prompt
