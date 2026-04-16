"""Small helpers for normalizing raw LLM text (reasoning models, etc.)."""

from __future__ import annotations

import re


def strip_think_tags(text: str) -> str:
    """Remove reasoning blocks (Qwen-style <think>...</think>)."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
