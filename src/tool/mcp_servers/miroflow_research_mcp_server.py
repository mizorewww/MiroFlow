# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio
from datetime import datetime
import os
from pathlib import Path
import re
import signal
import sys
import uuid

import dotenv
from fastmcp import FastMCP

from src.logging.live_trace import redact_secrets
from src.logging.logger import setup_mcp_logging


REPO_ROOT = Path(__file__).resolve().parents[3]

dotenv.load_dotenv(REPO_ROOT / ".env")
setup_mcp_logging(tool_name=os.path.basename(__file__))
mcp = FastMCP("miroflow-research-mcp-server")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _config_name() -> str:
    config_name = _env("MIROFLOW_MCP_CONFIG_NAME", "agent_hybrid_codex_deepseek")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config_name):
        raise ValueError(
            "MIROFLOW_MCP_CONFIG_NAME must be a config name, not a path."
        )
    return config_name


def _output_dir() -> str:
    return _env("MIROFLOW_MCP_OUTPUT_DIR", "logs/mcp")


def _timeout_seconds() -> int:
    try:
        return max(30, int(_env("MIROFLOW_MCP_TIMEOUT", "3600")))
    except ValueError:
        return 3600


def _build_task(question: str, context: str = "") -> str:
    question = (question or "").strip()
    context = (context or "").strip()
    if not question:
        raise ValueError("question is required.")
    if not context:
        return question
    return f"Context:\n{context}\n\nQuestion:\n{question}"


def _task_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"mcp_research_{timestamp}_{suffix}"


def _resolve_report_path(output_dir: str, task_id: str) -> Path:
    path = Path(output_dir)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path / f"{task_id}.md"


def _resolve_task_artifact_path(output_dir: str, task_id: str, suffix: str) -> Path:
    path = Path(output_dir)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path / f"{task_id}{suffix}"


def _read_tail(path: Path, limit: int = 4000) -> str:
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-limit:]
    except OSError:
        return ""


def _safe_write_report(path: Path, markdown: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
    except OSError:
        pass


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError:
        process.terminate()

    try:
        await asyncio.wait_for(process.wait(), timeout=5)
        return
    except asyncio.TimeoutError:
        pass

    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()
    await process.wait()


def _error_markdown(
    *,
    task_id: str,
    question: str,
    context: str,
    message: str,
    stdout: str = "",
    stderr: str = "",
    report_path: Path | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
) -> str:
    parts = [
        f"# MiroFlow MCP Error: {task_id}",
        "",
        "## Error",
        "",
        redact_secrets(message).strip(),
        "",
        "## Question",
        "",
        question.strip(),
    ]
    if context.strip():
        parts.extend(["", "## Context", "", context.strip()])
    if report_path is not None:
        parts.extend(["", "## Expected Report Path", "", f"`{report_path}`"])
    if stdout_path is not None or stderr_path is not None:
        parts.extend(["", "## Runtime Logs", ""])
        if stdout_path is not None:
            parts.append(f"- stdout: `{stdout_path}`")
        if stderr_path is not None:
            parts.append(f"- stderr: `{stderr_path}`")
    if stdout.strip():
        parts.extend(
            [
                "",
                "## Stdout Tail",
                "",
                "````text",
                redact_secrets(stdout.strip()[-4000:]),
                "````",
            ]
        )
    if stderr.strip():
        parts.extend(
            [
                "",
                "## Stderr Tail",
                "",
                "````text",
                redact_secrets(stderr.strip()[-4000:]),
                "````",
            ]
        )
    parts.append("")
    return "\n".join(parts)


async def _run_trace(question: str, context: str = "") -> str:
    task = _build_task(question, context)
    task_id = _task_id()
    config_name = _config_name()
    output_dir = _output_dir()
    report_path = _resolve_report_path(output_dir, task_id)
    stdout_path = _resolve_task_artifact_path(output_dir, task_id, ".stdout.log")
    stderr_path = _resolve_task_artifact_path(output_dir, task_id, ".stderr.log")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.setdefault("LOGGER_LEVEL", _env("MIROFLOW_MCP_LOGGER_LEVEL", "ERROR"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    if os.environ.get("MIROFLOW_MCP_UV_CACHE_DIR"):
        env["UV_CACHE_DIR"] = os.environ["MIROFLOW_MCP_UV_CACHE_DIR"]

    cmd = [
        sys.executable,
        "main.py",
        "trace",
        f"--config_file_name={config_name}",
        f"--task_id={task_id}",
        f"--task={task}",
        f"output_dir={output_dir}",
    ]

    with stdout_path.open("ab") as stdout_file, stderr_path.open("ab") as stderr_file:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(REPO_ROOT),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=_timeout_seconds())
        except asyncio.TimeoutError:
            await _terminate_process_group(process)
            markdown = _error_markdown(
                task_id=task_id,
                question=question,
                context=context,
                message=f"MiroFlow trace timed out after {_timeout_seconds()} seconds.",
                stdout=_read_tail(stdout_path),
                stderr=_read_tail(stderr_path),
                report_path=report_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            _safe_write_report(report_path, markdown)
            return markdown
        except asyncio.CancelledError:
            await _terminate_process_group(process)
            markdown = _error_markdown(
                task_id=task_id,
                question=question,
                context=context,
                message="MiroFlow trace was cancelled before completion, usually because the MCP client connection closed.",
                stdout=_read_tail(stdout_path),
                stderr=_read_tail(stderr_path),
                report_path=report_path,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            _safe_write_report(report_path, markdown)
            raise

    stdout_text = _read_tail(stdout_path)
    stderr_text = _read_tail(stderr_path)

    if report_path.exists():
        return report_path.read_text(encoding="utf-8")

    if process.returncode != 0:
        message = f"MiroFlow trace failed with exit code {process.returncode}."
    else:
        message = "MiroFlow trace finished, but the Markdown report was not created."
    markdown = _error_markdown(
        task_id=task_id,
        question=question,
        context=context,
        message=message,
        stdout=stdout_text,
        stderr=stderr_text,
        report_path=report_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )
    _safe_write_report(report_path, markdown)
    return markdown


@mcp.tool()
async def research(question: str, context: str = "") -> str:
    """Run the configured MiroFlow research agent and return the Markdown report.

    Args:
        question: The research question to answer. This is required.
        context: Optional background context for the question. Leave empty when not needed.

    Returns:
        The generated MiroFlow Markdown research report.
    """

    try:
        return await _run_trace(question=question, context=context)
    except Exception as error:
        return _error_markdown(
            task_id="mcp_research_startup_error",
            question=question,
            context=context,
            message=f"Failed to start MiroFlow research: {error}",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MiroFlow Research MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport method: 'stdio' or 'http' (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to use when running with HTTP transport (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("MIROFLOW_MCP_HOST", "127.0.0.1"),
        help="Host to bind when running with HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=os.environ.get("MIROFLOW_MCP_PATH", "/mcp"),
        help="URL path to use when running with HTTP transport (default: /mcp)",
    )
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            path=args.path,
            show_banner=False,
        )
