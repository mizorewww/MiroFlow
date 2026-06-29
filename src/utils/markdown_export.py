# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime
from pathlib import Path


def _fence(text: str) -> str:
    return "````text\n" + (text or "").strip() + "\n````"


def build_task_markdown(
    *,
    task_id: str,
    task_description: str,
    final_summary: str,
    final_boxed_answer: str,
    log_path: Path,
    config_name: str,
) -> str:
    generated_at = datetime.now().isoformat(timespec="seconds")
    return "\n".join(
        [
            f"# MiroFlow Task Report: {task_id}",
            "",
            "## Metadata",
            "",
            f"- Generated at: `{generated_at}`",
            f"- Config: `{config_name}`",
            f"- JSON trace: `{log_path}`",
            "",
            "## Task",
            "",
            task_description.strip(),
            "",
            "## Extracted Answer",
            "",
            _fence(final_boxed_answer),
            "",
            "## Final Summary",
            "",
            final_summary.strip(),
            "",
        ]
    )


def write_task_markdown(
    *,
    output_path: Path,
    task_id: str,
    task_description: str,
    final_summary: str,
    final_boxed_answer: str,
    log_path: Path,
    config_name: str,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_task_markdown(
            task_id=task_id,
            task_description=task_description,
            final_summary=final_summary,
            final_boxed_answer=final_boxed_answer,
            log_path=log_path,
            config_name=config_name,
        ),
        encoding="utf-8",
    )
    return output_path
