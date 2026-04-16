"""Deep-work self-evaluation prompt, JSON parsing, and multi-phase role pipeline."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from orqestra.core.llm_text import strip_think_tags

log = logging.getLogger(__name__)

# Roles the planner may emit (subset used per job).
_PLAN_ALLOWED_ROLES = frozenset(
    {"RESEARCHER", "CRITIC", "VALIDATOR", "WRITER", "ANALYST"},
)
_MAX_PLAN_PHASES = 8

_DELIVERABLE_REMEDIATION = (
    "You are the **completion agent** (remediation).\n"
    "A wiki page with **metadata.job_role: deliverable** is still missing.\n"
    "- Create or update with **kb_write** exactly **one** main results page and set "
    "**deliverable**; other pages remain **supporting**.\n"
    "- The page must clearly fulfill or summarize the assignment.\n"
)

# Prepended to phase 1 of deep-work jobs (task execution with RESEARCHER/CRITIC/VALIDATOR).
_DEEP_WORK_CONTEXT = """## Job context

- **Department** (organizational): `{department}` (label: {label})
  The department name describes this team's **function** (e.g. writing text, analyzing markets), **not** the topic of the assignment. The topic comes solely from the assignment itself.
- **Required**: Check the wiki (`kb_search`, `kb_list`, `kb_read`) before researching externally.
- **Outputs**: Save in the department wiki (`kb_write`). Mark exactly **one** main page as deliverable (`job_role: deliverable`); supporting pages as `supporting`.
- **Tags**: Every wiki page **must** have at least one **thematic tag** (e.g. `ki-pflegeheim`, `linkedin-strategie`, `seo-audit`) naming the concrete topic — not only generic tags like `ki` or `analyse`. Pages on the same topic must share the same thematic tag.

---
"""


def _deep_work_role_prompts() -> list[tuple[str, str]]:
    """Return (role_id, instruction) for each deep-work pipeline phase."""
    return [
        (
            "RESEARCHER",
            (
                "You are the **research and execution agent** (phase 1).\n"
                "- Execute the **assignment** below using appropriate tools (`kb_*`, `web_search`, `fetch_url`, …).\n"
                "- Document results in the wiki in a structured way.\n"
                "- Not the final handoff yet — deliver substantial intermediate results."
            ),
        ),
        (
            "CRITIC",
            (
                "You are the **critic** (phase 2).\n"
                "- Review the work so far against the **assignment**: completeness, quality, missing sources?\n"
                "- List concrete **gaps** and **priorities** for the next round."
            ),
        ),
        (
            "VALIDATOR",
            (
                "You are the **quality reviewer** (phase 3).\n"
                "- Check plausibility, consistency with the wiki, and fulfillment of the assignment.\n"
                "- What still needs follow-up?"
            ),
        ),
        (
            "RESEARCHER",
            (
                "You are again the **execution agent** (phase 4).\n"
                "- Close the gaps called out by criticism and validation.\n"
                "- Update or add wiki pages."
            ),
        ),
        (
            "CRITIC",
            (
                "You are the **critic** (phase 5).\n"
                "- **Final check**: Is the assignment substantively fulfilled? Redundancies, contradictions?\n"
                "- Brief assessment: ready to finish or still open points?"
            ),
        ),
        (
            "VALIDATOR",
            (
                "You are the **completion reviewer** (phase 6).\n"
                "- Ensure exactly **one** deliverable is clearly marked and the assignment is fulfilled.\n"
                "- Short **summary** for the user; no large new research rounds."
            ),
        ),
    ]


_DEEP_WORK_ROLES: list[tuple[str, str]] = _deep_work_role_prompts()

_DEEP_EVAL_PROMPT = (
    "Evaluate your work so far. Respond with ONLY a valid JSON object (no markdown fences):\n"
    '{"status": "GOAL_REACHED" or "CONTINUE",\n'
    ' "progress_pct": <integer 0-100>,\n'
    ' "summary": "<1-sentence summary of what was accomplished so far>",\n'
    ' "next_step": "<concrete next action — required when CONTINUE, empty string when GOAL_REACHED>"}\n\n'
    "GOAL_REACHED = the original task is fully complete, all wiki pages created/updated.\n"
    "CONTINUE = there are gaps, missing data, or incomplete steps.\n"
    "Do NOT use markdown code fences. Output raw JSON only."
)


def _parse_eval_result(text: str) -> dict:
    """Parse structured eval JSON from the model; fall back to legacy substring matching."""
    cleaned = strip_think_tags(text).strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "status" in obj:
            return {
                "status": obj.get("status", "CONTINUE"),
                "progress_pct": int(obj.get("progress_pct", 0)),
                "summary": str(obj.get("summary", "")),
                "next_step": str(obj.get("next_step", "")),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    if "GOAL_REACHED" in text:
        return {"status": "GOAL_REACHED", "progress_pct": 100, "summary": "", "next_step": ""}
    return {"status": "CONTINUE", "progress_pct": 0, "summary": "", "next_step": text}


def _format_chat_turns_for_prompt(turns: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for t in turns:
        kind = str(t.get("kind", ""))
        if kind == "chat-user":
            lines.append(f"User: {t.get('text', '')}")
        elif kind == "assistant":
            lines.append(f"Department: {t.get('text', '')}")
        elif kind == "system":
            lines.append(f"System: {t.get('text', '')}")
        elif kind == "user":
            task = t.get("task", "")
            jid = t.get("jobId", "")
            lines.append(f"User (job {jid}): {task}")
        else:
            lines.append(f"{kind or 'Turn'}: {t}")
    return "\n".join(lines).strip()


def formulate_job_task_from_chat(
    engine: Any,
    *,
    department_label: str,
    turns: list[dict[str, Any]],
) -> tuple[str, str]:
    """Use the LLM to turn a chat transcript into a concrete job task string.

    Returns (full_task, short_summary) for API responses.
    """
    transcript = _format_chat_turns_for_prompt(turns)
    if not transcript:
        raise ValueError("Empty chat transcript.")

    system = (
        "You formulate a clear **task** for a background job (deep work) from a department chat.\n"
        "The task must be understandable and actionable from the chat alone (wiki research, writing, analysis).\n"
        "Important: The department name describes the team's **function** (e.g. writing text), "
        "**not** the topic of the assignment. Derive the topic only from the chat content.\n"
        "Respond with **only one JSON object** (no markdown fences):\n"
        '{"task": "<full task description, same language as the chat>", "summary": "<max 120 chars>"}\n'
    )
    user = f"Department (organisatorisch): {department_label}\n\n--- Chat ---\n{transcript[:24000]}\n--- Ende ---\n"
    resp = engine.llm.chat.completions.create(
        model=engine.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
    )
    raw = (resp.choices[0].message.content or "").strip()
    data = _parse_json_object_loose(raw)
    task = str(data.get("task", "")).strip()
    summary = str(data.get("summary", "")).strip()
    if not task:
        raise ValueError("Model returned no task.")
    if not summary:
        summary = task[:120] + ("…" if len(task) > 120 else "")
    return task, summary


def _format_orchestrator_history_for_prompt(
    history: list[dict[str, Any]],
    draft_message: str | None,
) -> str:
    """Turn OpenAI-style session history into a transcript for job planning."""
    lines: list[str] = []
    for h in history:
        role = str(h.get("role", ""))
        content = str(h.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"User: {content[:24000]}")
        elif role == "assistant":
            lines.append(f"Orqestra: {content[:24000]}")
    dm = (draft_message or "").strip()
    if dm:
        lines.append(f"User (draft, not sent): {dm[:12000]}")
    return "\n".join(lines).strip()


def formulate_orchestrator_job(
    engine: Any,
    *,
    department_options: list[tuple[str, str]],
    history: list[dict[str, Any]],
    draft_message: str | None = None,
) -> tuple[str, str, str]:
    """Pick a department and formulate a task from orchestrator chat. Returns (dept_name, task, summary)."""
    if not department_options:
        raise ValueError("No departments configured.")

    allowed = {name for name, _ in department_options}
    dept_lines = "\n".join(f'- `{name}` — {label}' for name, label in department_options)
    transcript = _format_orchestrator_history_for_prompt(history, draft_message)
    if not transcript:
        raise ValueError("No chat content: write a message or use the draft.")

    system = (
        "You choose the **appropriate department** for a background job and formulate a clear **task**.\n"
        "The user is talking to the orchestrator; the task should be delegated to the chosen department.\n"
        "Pick **exactly one** department name from the list (technical `name` in backticks).\n"
        "The task must be understandable and actionable from the chat alone.\n"
        "Respond with **only one JSON object** (no markdown fences):\n"
        '{"department":"<technical name>", "task":"<full task, same language as chat>", '
        '"summary":"<max 120 chars>"}\n\n'
        "Available departments:\n"
        f"{dept_lines}\n"
    )
    user = f"--- Chat ---\n{transcript[:28000]}\n--- Ende ---\n"
    resp = engine.llm.chat.completions.create(
        model=engine.model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    raw = (resp.choices[0].message.content or "").strip()
    data = _parse_json_object_loose(raw)
    dept = str(data.get("department", "")).strip()
    task = str(data.get("task", "")).strip()
    summary = str(data.get("summary", "")).strip()
    if dept not in allowed:
        raise ValueError(
            f"Invalid department “{dept}”. Allowed: {', '.join(sorted(allowed))}",
        )
    if not task:
        raise ValueError("Model returned no task.")
    if not summary:
        summary = task[:120] + ("…" if len(task) > 120 else "")
    return dept, task, summary


def _parse_json_object_loose(raw: str) -> dict[str, Any]:
    cleaned = strip_think_tags(raw).strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    raise ValueError("No valid JSON for task/summary.")


def plan_roles(
    engine: Any,
    task: str,
    department_name: str,
    department_label: str,
) -> list[tuple[str, str]]:
    """Return (role_id, instruction) phases for this job; fallback to static pipeline."""
    system = (
        "You plan the **phases** of a deep-work job for a department.\n"
        "Each phase has a **role** and a short **instruction** (English) describing what happens in that phase.\n"
        "Allowed role IDs: RESEARCHER, CRITIC, VALIDATOR, WRITER, ANALYST.\n\n"
        "## Phase strategy\n"
        "1. **Initial research** (RESEARCHER): broad research and execution on the assignment.\n"
        "2. **Gap analysis** (ANALYST) — *for complex tasks*: synthesize prior results, "
        "identify open questions and missing aspects. No new research, analysis only.\n"
        "3. **Targeted follow-up research** (RESEARCHER): close concrete gaps from the analysis. "
        "Use multiple RESEARCHER phases with specific focus if needed.\n"
        "4. **Critique** (CRITIC): assess completeness, quality, and consistency.\n"
        "5. **Validation** (VALIDATOR): final check and ensure deliverable.\n"
        "Include WRITER for writing-heavy tasks.\n\n"
        "For **simple** tasks, 3–4 phases suffice (e.g. RESEARCHER → CRITIC → VALIDATOR). "
        "For **complex** topics use 5–8 phases with gap analysis and multiple research rounds.\n"
        "At least **3** phases, at most **8**.\n"
        "Respond with **only one JSON object**:\n"
        '{"phases":[{"role":"RESEARCHER","instruction":"..."}, ...]}\n'
    )
    user = (
        f"Department (organizational, NOT the topic): {department_label} ({department_name})\n\n"
        f"Assignment:\n{task[:12000]}\n"
    )
    try:
        resp = engine.llm.chat.completions.create(
            model=engine.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.5,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = _parse_json_object_loose(raw)
        phases_raw = data.get("phases")
        if not isinstance(phases_raw, list):
            raise ValueError("phases missing")
        out: list[tuple[str, str]] = []
        for ph in phases_raw:
            if not isinstance(ph, dict):
                continue
            role = str(ph.get("role", "")).strip().upper()
            instr = str(ph.get("instruction", "")).strip()
            if role not in _PLAN_ALLOWED_ROLES or not instr:
                continue
            out.append((role, instr))
        if len(out) < 3:
            raise ValueError("too few phases")
        if len(out) > _MAX_PLAN_PHASES:
            out = out[:_MAX_PLAN_PHASES]
        return out
    except Exception as exc:
        log.warning("plan_roles fallback to static pipeline: %s", exc)
        return list(_DEEP_WORK_ROLES)


def has_deliverable_event(events: list[Any]) -> bool:
    """True if any kb_write event recorded job_role deliverable."""
    for e in events:
        if getattr(e, "type", None) != "tool_call":
            continue
        if getattr(e, "name", None) != "kb_write":
            continue
        if not isinstance(getattr(e, "detail", None), dict):
            continue
        if getattr(e, "detail", {}).get("job_role") == "deliverable":
            return True
    return False


def deliverable_remediation_phase() -> tuple[str, str]:
    """Extra phase when no deliverable kb_write was recorded."""
    return ("VALIDATOR", _DELIVERABLE_REMEDIATION)
