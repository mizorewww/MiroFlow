# SPDX-FileCopyrightText: 2025 MiromindAI
#
# SPDX-License-Identifier: Apache-2.0

import json
import os
import re
import sys
from datetime import datetime
from typing import Any


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

SECRET_PATTERNS = (
    (
        re.compile(
            r"(?i)(api[_-]?key|token|authorization|secret|password)"
            r"(['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"), r"\1[REDACTED]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_\-]{12,})\b"), "[REDACTED]"),
    (re.compile(r"\b(jina_[A-Za-z0-9_\-]{12,})\b"), "[REDACTED]"),
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def is_live_trace_enabled() -> bool:
    return _env_flag("MIROFLOW_LIVE_TRACE", False)


def is_live_reasoning_enabled() -> bool:
    if os.getenv("MIROFLOW_LIVE_REASONING") is not None:
        return _env_flag("MIROFLOW_LIVE_REASONING", False)
    return is_live_trace_enabled()


def _max_chars() -> int:
    try:
        return max(200, int(os.getenv("MIROFLOW_LIVE_TRACE_MAX_CHARS", "6000")))
    except ValueError:
        return 6000


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def format_live_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def emit_live_trace(
    event: str,
    title: str,
    content: Any = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not is_live_trace_enabled():
        return
    if event == "reasoning" and not is_live_reasoning_enabled():
        return

    pieces = []
    if metadata:
        pieces.append(format_live_value(metadata))
    body = format_live_value(content)
    if body:
        pieces.append(body)

    text = redact_secrets("\n\n".join(pieces).strip())
    limit = _max_chars()
    if len(text) > limit:
        text = text[:limit] + "\n... [live trace truncated]"

    timestamp = datetime.now().isoformat(timespec="seconds")
    header = f"[MIROFLOW LIVE][{timestamp}][{event}] {title}"
    output = f"\n{header}\n{'-' * min(len(header), 88)}"
    if text:
        output += f"\n{text}"
    output += "\n"

    sys.stdout.write(output)
    sys.stdout.flush()
