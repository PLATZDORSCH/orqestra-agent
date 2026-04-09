"""Conversation loop — connects the LLM to capabilities.

StrategyEngine runs a synchronous loop:
  1. Send messages to the LLM (including capability schemas)
  2. If tool_calls come back: execute them, append results, go to 1
  3. If text response: return it

Works with any OpenAI-compatible API (OpenAI, Ollama, vLLM, LiteLLM, etc.).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from core.capabilities import CapabilityManager

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent


class StrategyEngine:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        capabilities: CapabilityManager,
        *,
        persona_path: str | Path | None = None,
        memory_prompt: str | None = None,
        max_rounds: int = 25,
        language: str | None = None,
        on_thinking: Callable[[str], None] | None = None,
        on_tool_call: Callable[[str, str], None] | None = None,
        on_tool_done: Callable[[], None] | None = None,
    ) -> None:
        self.llm = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.capabilities = capabilities
        self.max_rounds = max_rounds
        self._persona = self._load_persona(persona_path)
        self._memory_prompt = memory_prompt
        self._language = language
        self._on_thinking = on_thinking
        self._on_tool_call = on_tool_call
        self._on_tool_done = on_tool_done

    def run(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Answer a question, potentially using multiple tool rounds."""
        messages = self._build_messages(question, history)
        tools = self.capabilities.schemas()

        for round_num in range(1, self.max_rounds + 1):
            log.debug("Round %d/%d", round_num, self.max_rounds)

            if self._on_thinking:
                self._on_thinking("Thinking")

            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
            )
            choice = response.choices[0]
            assistant_msg = choice.message
            messages.append(assistant_msg)

            if not assistant_msg.tool_calls:
                if self._on_tool_done:
                    self._on_tool_done()
                return assistant_msg.content or ""

            for call in assistant_msg.tool_calls:
                fn_name = call.function.name
                fn_args = json.loads(call.function.arguments)
                args_preview = _truncate(json.dumps(fn_args, ensure_ascii=False), 80)

                if self._on_tool_call:
                    self._on_tool_call(fn_name, args_preview)

                if self._on_thinking:
                    self._on_thinking(f"Running {fn_name}")

                result = self.capabilities.run(fn_name, fn_args)
                log.debug("← %s: %s chars", fn_name, len(result))

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

        if self._on_tool_done:
            self._on_tool_done()
        return "Could not complete the analysis — round limit reached."

    def _build_messages(
        self,
        question: str,
        history: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        # Single system message — some OpenAI-compatible backends (e.g. vLLM via LiteLLM)
        # reject multiple role=system blocks and require system at the very beginning only.
        parts: list[str] = []
        if self._persona:
            parts.append(self._persona)
        if self._language:
            parts.append(
                f"## Language\n\n"
                f"Your default language is {self._language}. "
                f"Use {self._language} when the user's language is ambiguous or unclear. "
                f"However, if the user writes in a different language, always respond "
                f"in that language instead — mirror the user's language exactly."
            )
        if self._memory_prompt:
            parts.append(
                "## Long-term memory (wiki/memory.md)\n\n"
                f"{self._memory_prompt}\n\n"
                "Update this file with `kb_write` when the user agrees on lasting preferences or facts. "
                "Do not paste long analyses here — write a wiki page and link to it."
            )
        if parts:
            messages.append({"role": "system", "content": "\n\n".join(parts)})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})
        return messages

    def _load_persona(self, path: str | Path | None) -> str:
        if path is None:
            path = _ROOT / "personas" / "strategist.md"
        path = Path(path)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        log.warning("Persona file not found: %s", path)
        return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
