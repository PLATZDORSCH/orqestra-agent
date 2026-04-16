"""Token estimation for context-window management.

Uses tiktoken when available (accurate for OpenAI-family models), otherwise
falls back to a character-based heuristic (~1 token per 3 chars, conservative
for German / mixed-language text).

Handles both plain dicts and OpenAI SDK message objects, including tool_calls
structures and tool-schema overhead.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    _USE_TIKTOKEN = True
except Exception:
    _enc = None
    _USE_TIKTOKEN = False

_CHARS_PER_TOKEN = 3
_MSG_OVERHEAD = 4
_REPLY_PRIMING = 3
_TOOL_CALL_OVERHEAD = 8  # id, type, function structure per call


def estimate_text(text: str) -> int:
    if _USE_TIKTOKEN and _enc is not None:
        return len(_enc.encode(text))
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _estimate_tool_calls(tool_calls: list | None) -> int:
    """Estimate tokens consumed by tool_calls in an assistant message."""
    if not tool_calls:
        return 0
    total = 0
    for tc in tool_calls:
        total += _TOOL_CALL_OVERHEAD
        if isinstance(tc, dict):
            fn = tc.get("function", {})
            total += estimate_text(fn.get("name", ""))
            total += estimate_text(fn.get("arguments", ""))
        else:
            total += estimate_text(tc.function.name)
            total += estimate_text(tc.function.arguments)
    return total


def estimate_messages(messages: list[Any]) -> int:
    """Estimate total tokens for an OpenAI-style message list.

    Works with plain dicts and OpenAI SDK ChatCompletionMessage objects.
    Counts content, tool_calls (name + arguments), and structural overhead.
    """
    total = 0
    for msg in messages:
        content = _get_attr(msg, "content") or ""
        if isinstance(content, str):
            total += estimate_text(content)

        tool_calls = _get_attr(msg, "tool_calls")
        total += _estimate_tool_calls(tool_calls)

        total += _MSG_OVERHEAD
    return total + _REPLY_PRIMING


def estimate_tool_schemas(schemas: list[dict]) -> int:
    """Estimate tokens consumed by the tools parameter sent with each API call.

    Each schema is serialized to JSON by the API; we estimate that cost once
    so the engine can factor it into the context-window budget.
    """
    if not schemas:
        return 0
    text = json.dumps(schemas, ensure_ascii=False)
    return estimate_text(text)
