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
from typing import Any

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
        max_rounds: int = 25,
    ) -> None:
        self.llm = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.capabilities = capabilities
        self.max_rounds = max_rounds
        self._persona = self._load_persona(persona_path)

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

            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
            )
            choice = response.choices[0]
            assistant_msg = choice.message
            messages.append(assistant_msg)

            if not assistant_msg.tool_calls:
                return assistant_msg.content or ""

            for call in assistant_msg.tool_calls:
                fn_name = call.function.name
                fn_args = json.loads(call.function.arguments)
                log.info("→ %s(%s)", fn_name, _truncate(json.dumps(fn_args, ensure_ascii=False), 120))

                result = self.capabilities.run(fn_name, fn_args)
                log.info("← %s chars", len(result))

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

        return "Could not complete the analysis — round limit reached."

    def _build_messages(
        self,
        question: str,
        history: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if self._persona:
            messages.append({"role": "system", "content": self._persona})
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
