"""Conversation loop — connects the LLM to capabilities.

StrategyEngine runs a synchronous loop:
  1. Send messages to the LLM (including capability schemas)
  2. If tool_calls come back: execute them, append results, go to 1
  3. If text response: return it

Includes automatic context-window management:
  - Monitors token usage against a configurable limit
  - Saves tool results to wiki before compressing (auto-snapshot)
  - Compresses mid-loop when threshold is reached
  - Works for both the orchestrator REPL and background department jobs

Works with any OpenAI-compatible API (OpenAI, Ollama, vLLM, LiteLLM, etc.).
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from orqestra._paths import REPO_ROOT as _ROOT
from orqestra.core.capabilities import CapabilityManager
from orqestra.core.research_budget import ResearchBudget, web_search_result_counts_toward_budget
from orqestra.core.tokens import estimate_messages, estimate_text, estimate_tool_schemas

log = logging.getLogger(__name__)


def _merge_job_context_into_kb_write_args(
    fn_args: dict[str, Any],
    job_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Inject job_id (and default job_role) into kb_write metadata for department jobs."""
    if not job_context:
        return fn_args
    jid = job_context.get("job_id")
    if not jid:
        return fn_args
    out = dict(fn_args)
    md_raw = out.get("metadata")
    if md_raw is None:
        md: dict[str, Any] = {}
    elif isinstance(md_raw, dict):
        md = dict(md_raw)
    elif isinstance(md_raw, str):
        s = md_raw.strip()
        if not s:
            md = {}
        else:
            try:
                parsed = json.loads(s)
                md = dict(parsed) if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                md = {}
    else:
        md = {}
    md.setdefault("job_id", jid)
    md.setdefault("job_role", "supporting")
    out["metadata"] = md
    return out

_SNAPSHOT_TOOL_RESULT_LIMIT = 5000
_SNAPSHOT_ASSISTANT_LIMIT = 3000
_SNAPSHOT_USER_LIMIT = 2000


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
        project_context: str | None = None,
        max_rounds: int = 25,
        language: str | None = None,
        context_window: int = 0,
        summarize_at: float = 0.7,
        on_thinking: Callable[[str, str], None] | None = None,
        on_tool_call: Callable[..., None] | None = None,
        on_tool_done: Callable[[], None] | None = None,
    ) -> None:
        self.llm = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.capabilities = capabilities
        self.max_rounds = max_rounds
        if persona_path is None:
            self._persona_path = _ROOT / "personas" / "orchestrator.md"
        else:
            self._persona_path = Path(persona_path).resolve()
        self._persona = self._load_persona(self._persona_path, language)
        self._memory_prompt = memory_prompt
        self._project_context = project_context
        self._language = language
        self._context_window = context_window
        self._summarize_at = summarize_at
        self._on_thinking = on_thinking
        self._on_tool_call = on_tool_call
        self._on_tool_done = on_tool_done
        self._tool_schema_tokens: int | None = None
        self._persona_dirty = threading.Event()

    def invalidate_persona(self) -> None:
        """Mark orchestrator persona as stale; next ``run()`` / ``_build_messages`` reloads from disk."""
        self._persona_dirty.set()

    def _ensure_persona_fresh(self) -> None:
        if self._persona_dirty.is_set():
            self._persona = self._load_persona(self._persona_path, self._language)
            self._persona_dirty.clear()

    def reload_persona(self) -> None:
        """Re-read persona markdown from disk immediately (backward compatible)."""
        self.invalidate_persona()
        self._ensure_persona_fresh()

    def invalidate_tool_schema_cache(self) -> None:
        """Call after orchestrator capabilities change (delegate / department tools)."""
        self._tool_schema_tokens = None

    # ------------------------------------------------------------------
    # Main conversation loop
    # ------------------------------------------------------------------

    def run(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
        *,
        stop_event: threading.Event | None = None,
        on_tool_call: Callable[..., None] | None = None,
        on_thinking: Callable[[str, str], None] | None = None,
        job_context: dict[str, Any] | None = None,
        research_budget: ResearchBudget | None = None,
    ) -> str:
        """Answer a question, potentially using multiple tool rounds.

        Per-call *on_tool_call* / *on_thinking* override instance-level callbacks
        (useful for Telegram gateway where each request needs its own handler).
        If *stop_event* is set between rounds or between tool calls, return a
        cancellation message (cooperative stop for background department jobs).

        *job_context*: optional dict with ``job_id`` for background jobs; ``kb_write``
        calls get ``metadata.job_id`` and default ``metadata.job_role=supporting``.

        *research_budget*: optional per-job limiter for ``web_search`` (background jobs).
        """
        _thinking = on_thinking or self._on_thinking
        _tool_call = on_tool_call or self._on_tool_call

        messages = self._build_messages(question, history)
        tools = self.capabilities.schemas()

        if self._tool_schema_tokens is None:
            self._tool_schema_tokens = estimate_tool_schemas(tools)
            log.debug("Tool schema overhead: ~%d tokens", self._tool_schema_tokens)

        for round_num in range(1, self.max_rounds + 1):
            log.debug("Round %d/%d", round_num, self.max_rounds)

            if stop_event and stop_event.is_set():
                return "[Job cancelled by user]"

            if self._context_window and round_num > 1:
                est = estimate_messages(messages) + self._tool_schema_tokens
                threshold = int(self._context_window * self._summarize_at)
                if est >= threshold:
                    messages = self._compress_in_loop(messages, est)

            response = self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
            )
            choice = response.choices[0]
            assistant_msg = choice.message
            messages.append(assistant_msg)

            if _thinking:
                raw = (assistant_msg.content or "").strip()
                preview = (raw[:500] + "…") if len(raw) > 500 else raw
                _thinking("Thinking", preview)

            if not assistant_msg.tool_calls:
                if self._on_tool_done:
                    self._on_tool_done()
                return assistant_msg.content or ""

            for call in assistant_msg.tool_calls:
                if stop_event and stop_event.is_set():
                    return "[Job cancelled by user]"

                fn_name = call.function.name
                fn_args = json.loads(call.function.arguments)
                if fn_name in ("kb_write", "my_kb_write") and job_context:
                    fn_args = _merge_job_context_into_kb_write_args(fn_args, job_context)
                args_preview = _truncate(json.dumps(fn_args, ensure_ascii=False), 80)

                if _tool_call:
                    _tool_call(fn_name, args_preview, fn_args)

                if _thinking:
                    _thinking(f"Tool: {fn_name}", args_preview)

                if research_budget and fn_name == "web_search":
                    kind, payload = research_budget.consume(fn_name, fn_args)
                    if kind == "cache":
                        assert payload is not None
                        result = payload
                    elif kind == "exhausted":
                        assert payload is not None
                        result = payload
                    else:
                        result = self.capabilities.run(fn_name, fn_args)
                        if web_search_result_counts_toward_budget(result):
                            research_budget.record_successful_search()
                        research_budget.store(fn_name, fn_args, result)
                else:
                    result = self.capabilities.run(fn_name, fn_args)
                log.debug("\u2190 %s: %s chars", fn_name, len(result))

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                })

        if self._on_tool_done:
            self._on_tool_done()
        return "Could not complete the analysis \u2014 round limit reached."

    # ------------------------------------------------------------------
    # Message building
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        question: str,
        history: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        self._ensure_persona_fresh()
        messages: list[dict[str, Any]] = []
        parts: list[str] = []
        if self._persona:
            parts.append(self._persona)
        parts.append(_reference_datetime_section())
        parts.append(_skill_wiki_policy_section())
        if self._project_context:
            parts.append(f"## Project context\n\n{self._project_context}")
        if self._language:
            parts.append(
                f"## Language\n\n"
                f"Your default language is {self._language}. "
                f"Use {self._language} when the user's language is ambiguous or unclear. "
                f"However, if the user writes in a different language, always respond "
                f"in that language instead \u2014 mirror the user's language exactly."
            )
        if self._memory_prompt:
            parts.append(
                "## Long-term memory (wiki/memory.md)\n\n"
                f"{self._memory_prompt}\n\n"
                "Update this file with `kb_write` when the user agrees on lasting preferences or facts. "
                "Do not paste long analyses here \u2014 write a wiki page and link to it."
            )
        parts.append(
            "## Formatting\n\n"
            "Do NOT use emojis or emoticons in any output — not in chat replies, "
            "wiki pages, reports, summaries, or any other generated text. "
            "Use clear, professional language without decorative symbols."
        )
        if parts:
            messages.append({"role": "system", "content": "\n\n".join(parts)})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": question})
        return messages

    # ------------------------------------------------------------------
    # Context-window management \u2014 REPL-level (between turns)
    # ------------------------------------------------------------------

    def summarize_if_needed(
        self,
        history: list[dict[str, Any]],
        *,
        active_jobs: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Check token budget; if over threshold, compress *history* via LLM summary.

        Saves a snapshot of the conversation to the wiki before compressing.
        Returns the (possibly condensed) history.
        """
        if not self._context_window or not history:
            return history

        self._ensure_persona_fresh()
        threshold = int(self._context_window * self._summarize_at)

        schema_tokens = self._tool_schema_tokens or 0
        system_tokens = estimate_text(self._persona) + estimate_text(self._memory_prompt or "")
        history_tokens = estimate_messages(history)
        total = system_tokens + history_tokens + schema_tokens

        if total < threshold:
            return history

        log.info(
            "Context window %.0f%% full (%d/%d tokens) \u2014 summarizing conversation",
            total / self._context_window * 100, total, self._context_window,
        )

        snapshot_path = self._save_snapshot(history, prefix="conversation-snapshot")

        jobs_section = ""
        if active_jobs:
            lines = ["", "## Running background jobs (do not forget!)"]
            for j in active_jobs:
                lines.append(
                    f"- **{j['job_id']}** ({j['department']}): "
                    f"{j['task'][:120]} \u2014 Status: {j['status']}"
                )
            jobs_section = "\n".join(lines)

        snapshot_note = ""
        if snapshot_path:
            snapshot_note = (
                f"\n\nThe full conversation history was saved under "
                f"`{snapshot_path}`."
            )

        summary_prompt = (
            "Summarize the conversation so far concisely (max. 800 words). "
            "Keep: all decisions made, open questions, results, "
            "important numbers/URLs, and the current work state. "
            "Write the summary as a briefing for yourself so you can "
            "continue seamlessly."
            f"{jobs_section}{snapshot_note}"
        )

        summary_messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are an assistant that summarizes conversations."},
            *history,
            {"role": "user", "content": summary_prompt},
        ]

        try:
            if self._on_thinking:
                self._on_thinking("Summarizing conversation", "")
            resp = self.llm.chat.completions.create(
                model=self.model,
                messages=summary_messages,
            )
            summary_text = resp.choices[0].message.content or ""
        except Exception:
            log.exception("Summarization failed \u2014 keeping full history")
            return history

        condensed: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    "[Automatic conversation summary \u2014 context window was "
                    f"{total / self._context_window * 100:.0f}% full]\n\n"
                    f"{summary_text}"
                    + (f"\n\n\u2192 Full history: `{snapshot_path}`" if snapshot_path else "")
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Understood. I have read the summary and will continue seamlessly. "
                    "I am aware of all running jobs and open items."
                ),
            },
        ]

        log.info(
            "History compressed: %d messages (%d tokens) \u2192 2 messages (%d tokens)",
            len(history), history_tokens, estimate_messages(condensed),
        )
        return condensed

    # ------------------------------------------------------------------
    # Context-window management \u2014 in-loop (during tool rounds)
    # ------------------------------------------------------------------

    def _compress_in_loop(
        self,
        messages: list[dict[str, Any] | Any],
        current_tokens: int,
    ) -> list[dict[str, Any]]:
        """Compress the in-flight message array when approaching the context limit.

        1. Saves all tool results as a wiki snapshot (auto-snapshot)
        2. Generates a summary of work done so far via LLM
        3. Returns a compressed message list (system + summary + ack)
        """
        log.info(
            "In-loop compression triggered at %d/%d tokens (%.0f%%)",
            current_tokens, self._context_window,
            current_tokens / self._context_window * 100,
        )

        if self._on_thinking:
            self._on_thinking("Saving snapshot & compressing", "")

        snapshot_path = self._save_snapshot(messages, prefix="tool-snapshot")

        # Separate system message
        system_msg = None
        start = 0
        if messages and _get_role(messages[0]) == "system":
            system_msg = messages[0]
            start = 1

        # Build a serializable conversation for the summary LLM call
        conv_for_summary: list[dict[str, Any]] = [
            {"role": "system", "content": "Summarize the work done so far."},
        ]
        for msg in messages[start:]:
            role = _get_role(msg)
            text = _get_content(msg)
            if role == "tool":
                conv_for_summary.append({
                    "role": "user",
                    "content": f"[Tool result]\n{text[:800]}",
                })
            elif role in ("user", "assistant") and text:
                conv_for_summary.append({
                    "role": role,
                    "content": text[:1500],
                })
            elif role == "assistant":
                tc_names = _get_tool_call_names(msg)
                if tc_names:
                    conv_for_summary.append({
                        "role": "assistant",
                        "content": f"[Tool calls: {tc_names}]",
                    })

        snapshot_note = ""
        if snapshot_path:
            snapshot_note = (
                f"\n\nFull tool outputs were saved under "
                f"`{snapshot_path}`. Use `kb_read` if you need to review them."
            )

        conv_for_summary.append({
            "role": "user",
            "content": (
                "Summarize the work done so far concisely (max. 600 words). "
                "Keep: the original task, all results and insights so far, "
                "and open next steps."
                f"{snapshot_note}"
            ),
        })

        try:
            resp = self.llm.chat.completions.create(
                model=self.model,
                messages=conv_for_summary,
            )
            summary_text = resp.choices[0].message.content or ""
        except Exception:
            log.exception("In-loop compression failed \u2014 continuing with full messages")
            return messages

        # Rebuild clean message list
        compressed: list[dict[str, Any]] = []
        if system_msg:
            compressed.append(
                system_msg if isinstance(system_msg, dict)
                else {"role": "system", "content": _get_content(system_msg)}
            )
        compressed.append({
            "role": "user",
            "content": (
                f"[Automatic mid-run summary \u2014 {current_tokens} tokens reached]\n\n"
                f"{summary_text}"
                + (f"\n\n\u2192 Snapshot: `{snapshot_path}`" if snapshot_path else "")
            ),
        })
        compressed.append({
            "role": "assistant",
            "content": "Understood. I will continue seamlessly using this summary.",
        })

        new_tokens = estimate_messages(compressed)
        log.info(
            "In-loop compressed: %d \u2192 %d messages (%d \u2192 %d tokens)",
            len(messages), len(compressed), current_tokens, new_tokens,
        )
        return compressed

    # ------------------------------------------------------------------
    # Auto-snapshot \u2014 save messages to wiki before compression
    # ------------------------------------------------------------------

    def _save_snapshot(
        self,
        messages: list[dict[str, Any] | Any],
        *,
        prefix: str = "snapshot",
    ) -> str | None:
        """Extract tool results + conversation and save as a wiki page.

        Returns the wiki path on success, None if kb_write is unavailable.
        """
        if "kb_write" not in self.capabilities.names():
            log.debug("No kb_write capability \u2014 skipping snapshot")
            return None

        sections: list[str] = []
        for msg in messages:
            role = _get_role(msg)
            text = _get_content(msg)
            if role == "system":
                continue
            elif role == "tool":
                sections.append(
                    f"### Tool Result\n\n```\n"
                    f"{text[:_SNAPSHOT_TOOL_RESULT_LIMIT]}\n```"
                )
            elif role == "assistant":
                tc_names = _get_tool_call_names(msg)
                if tc_names:
                    sections.append(f"### Tool-Aufrufe: {tc_names}")
                if text:
                    sections.append(
                        f"### Assistant\n\n{text[:_SNAPSHOT_ASSISTANT_LIMIT]}"
                    )
            elif role == "user" and text:
                sections.append(f"### User\n\n{text[:_SNAPSHOT_USER_LIMIT]}")

        if not sections:
            return None

        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        path = f"wiki/ergebnisse/{prefix}-{ts}.md"
        body = f"# Auto-Snapshot ({ts})\n\n" + "\n\n---\n\n".join(sections)
        metadata = {
            "title": f"Auto-Snapshot {ts}",
            "category": "ergebnisse",
            "tags": ["auto-snapshot", "context-window"],
        }

        try:
            self.capabilities.run(
                "kb_write",
                {"path": path, "metadata": metadata, "content": body},
            )
            log.info("Snapshot saved: %s (%d sections)", path, len(sections))
            return path
        except Exception:
            log.exception("Snapshot save failed")
            return None

    # ------------------------------------------------------------------

    def _load_persona(self, path: str | Path | None, language: str | None = None) -> str:
        if path is None:
            path = _ROOT / "personas" / "orchestrator.md"
        path = Path(path)
        # Locale fallback: if language is German, try .de.md first
        if language and language.lower().startswith("de"):
            locale_path = path.with_suffix(".de.md")
            if locale_path.is_file():
                return locale_path.read_text(encoding="utf-8").strip()
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        log.warning("Persona file not found: %s", path)
        return ""


# ======================================================================
# Helpers — work with both plain dicts and OpenAI message objects
# ======================================================================

def _get_role(msg: dict | Any) -> str | None:
    if isinstance(msg, dict):
        return msg.get("role")
    return getattr(msg, "role", None)


def _get_content(msg: dict | Any) -> str:
    c = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    return c or ""


def _get_tool_call_names(msg: dict | Any) -> str:
    tcs = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
    if not tcs:
        return ""
    names: list[str] = []
    for tc in tcs:
        if isinstance(tc, dict):
            names.append(tc.get("function", {}).get("name", "?"))
        else:
            names.append(tc.function.name)
    return ", ".join(names)


def _reference_datetime_section() -> str:
    now = datetime.now().astimezone()
    d = now.date().isoformat()
    return (
        "## Current reference (server)\n\n"
        f"- **Calendar date for analyses (\u201ctoday\u201d, \u201cas of\u201d, trends):** {d}\n"
        f"- **Timestamp (local, ISO-8601):** {now.isoformat(timespec='seconds')}\n\n"
        "Use this date for all date-related statements and assessments. "
        "When saving to the wiki (`kb_write`): set `created` and `updated` in the YAML front matter "
        "to this calendar date (or omit them \u2014 they will be set on write)."
    )


def _skill_wiki_policy_section() -> str:
    return (
        "## Research order \u2014 mandatory\n\n"
        "For **every** substantive question, follow this order:\n"
        "1. **Wiki first**: `kb_search` (and optionally `cross_department_search`) \u2014 check whether "
        "the answer is already in the knowledge base. If yes, answer from it. "
        "For relevant hits from `cross_department_search`, load the full page with "
        "`cross_department_read`.\n"
        "2. **Web research for gaps**: Only if the wiki has no or insufficient results, use "
        "`web_search` / `fetch_url`.\n"
        "3. **Model knowledge as supplement only**: Your internal knowledge is for structuring "
        "and framing \u2014 **never** the primary factual source for numbers, URLs, or "
        "claims about companies/markets.\n"
        "4. **Persist new findings**: Save web research results with `kb_write` in the wiki "
        "so they are available next time.\n\n"
        "## Skills & wiki \u2014 mandatory\n\n"
        "If you have loaded and executed a procedure with **`skill_read`** (e.g. SEO audit, "
        "analysis playbook, checklists), you must then store the **finished result** with **`kb_write`** "
        "in the appropriate wiki \u2014 not only in the chat reply. "
        "Typical paths: `wiki/ergebnisse/<short-description>-YYYY-MM-DD.md`, `wiki/wissen/...`, "
        "or for departments `departments/<name>/knowledge_base/wiki/...`. "
        "Use front matter with `title`, `category`, `tags`, relevant URLs/sources; link related pages. "
        "Without `kb_write`, the analysis is incomplete.\n\n"
        "## Wiki maintenance \u2014 automatic\n\n"
        "**`wiki/index.md`** (catalog and stats) and **`wiki/log.md`** are updated **automatically** by "
        "the system after each `kb_write` \u2014 do **not** edit them manually.\n\n"
        "## Skill separation \u2014 mandatory\n\n"
        "The **Orchestrator** (you) may only use `skill_create`/`skill_update` for "
        "cross-cutting orchestrator skills (wiki management, stakeholder mapping, "
        "OKR, proposals, risk assessment, etc.).\n"
        "**Domain-specific skills** (e.g. SEO, marketing, strategy, finance, operations) belong in "
        "the relevant department. If a new domain skill is needed, **delegate** skill creation to "
        "that department (via `delegate`).\n"
        "This separation avoids duplicates and keeps context lean.\n\n"
        "## Skill \u2260 content \u2014 mandatory\n\n"
        "A skill is a **reusable procedure** (recipe, playbook, method). "
        "The **output** of a skill (e.g. a social post, analysis, report) "
        "is **not** a new skill; it belongs in the wiki (`kb_write`). "
        "Create a skill ONLY if it describes a **genuinely new, repeatable method** "
        "that does not already exist. Ask: does this describe **how** to do something, "
        "or **what** was produced? "
        "If the latter \u2192 `kb_write`, not `skill_create`."
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
