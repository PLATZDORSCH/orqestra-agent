"""Proactive multi-phase pipeline prompts (Researcher / Critic / Validator)."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from orqestra.core.proactive_models import Mission, effective_proactive

if TYPE_CHECKING:
    from orqestra.core.department import Department
    from orqestra.core.job_store import JobStore

_PROACTIVE_PROMPT = (
    "Proactive multi-phase run (Researcher / Critic / Validator): "
    "autonomous research and **concrete wiki outputs** for department **{department}**."
)

# Context block prepended to phase 1. Use .format(department=..., label=...).
_PROACTIVE_CONTEXT = """## Proactive context

- **Department** (organizational): `{department}` (label: {label})
  The department name describes this team's **function**, not a subject area.
- **Goal**: Find new, actionable content that fits the department's scope and
  is **not** already covered in depth in the wiki.
- **Required**: `kb_read` on `wiki/memory.md` (if present) and at least one
  `kb_search`/`kb_list` query in the **department wiki** before researching externally.
- **Web**: Use `web_search` and optionally `fetch_url` for current developments.
- **Save artifacts**: Only in the **last phase** with `kb_write` — until then only collect,
  verify, and structure. Write results as Markdown under appropriate paths
  (e.g. `wiki/wissen/...`, `wiki/ergebnisse/...`, `content/drafts/...` depending on template).
- **At most 2** new wiki pages total in phase 6: one thorough main page
  (`job_role: deliverable`) and optionally one supporting page (`supporting`).
- **Tags**: Every wiki page **must** have at least one **thematic tag** (e.g. `ki-pflegeheim`, `linkedin-strategie`, `seo-audit`) naming the concrete topic — not only generic tags like `ki` or `analyse`. Pages on the same topic must share the same thematic tag.

---
"""


def format_proactive_context(department: str, label: str, mission: Mission | None = None) -> str:
    """Build the context block for proactive phase 1 (optional mission focus)."""
    base = _PROACTIVE_CONTEXT.format(department=department, label=label)
    if mission is None or not (mission.prompt or "").strip():
        return base
    mission_block = (
        "## Mission (this run)\n\n"
        f"- **ID**: `{mission.id}`\n"
        f"- **Label**: {mission.label or mission.id}\n\n"
        f"**Focus / instructions:**\n\n{mission.prompt.strip()}\n\n---\n\n"
    )
    return mission_block + base


def pick_missions_for_run(
    dept: Department,
    job_store: JobStore | None,
    *,
    mission_id: str | None = None,
) -> list[Mission]:
    """Select which mission(s) to run for this proactive tick.

    Returns empty list when no missions are defined (caller uses generic ``_PROACTIVE_PROMPT``).

    - *mission_id* set: run exactly that mission (if it exists).
    - *mission_id* ``\"__all__\"``: run all missions as separate jobs (scheduler uses this).
    - Otherwise: apply *strategy* (rotate / random / all) on configured missions.
    """
    cfg = effective_proactive(dept.proactive)
    missions = cfg.missions
    if not missions:
        return []

    if mission_id:
        mid = mission_id.strip()
        if mid == "__all__":
            return list(missions)
        for m in missions:
            if m.id == mid:
                return [m]
        return []

    strat = cfg.strategy
    if strat == "all":
        return list(missions)
    if strat == "random":
        return [random.choice(missions)]

    # rotate
    n = len(missions)
    if job_store is None:
        return [missions[0]]
    idx = job_store.get_proactive_mission_index(dept.name) % n
    chosen = missions[idx]
    job_store.set_proactive_mission_index(dept.name, (idx + 1) % n)
    return [chosen]


def resolve_mission_for_job(dept: Department, job: object) -> Mission | None:
    """Look up the ``Mission`` object from the job's stored mission id."""
    mid_raw = getattr(job, "proactive_mission_id", None)
    if not mid_raw:
        return None
    cfg = effective_proactive(dept.proactive)
    mid = str(mid_raw).strip()
    for m in cfg.missions:
        if m.id == mid:
            return m
    return None


def proactive_task_text(
    department_name: str,
    mission: Mission | None,
) -> str:
    """User-visible task string stored on the job (and shown in UI)."""
    if mission is not None and mission.prompt.strip():
        return (
            f"Proactive mission `{mission.id}` ({mission.label or mission.id}): "
            f"{mission.prompt.strip()[:500]}"
            + ("…" if len(mission.prompt.strip()) > 500 else "")
        )
    return _PROACTIVE_PROMPT.format(department=department_name)


def _proactive_role_prompts() -> list[tuple[str, str]]:
    """Return (role_id, instruction) for each pipeline phase."""
    return [
        (
            "RESEARCHER",
            (
                "You are the **research agent** (phase 1).\n"
                "- Use `kb_search`, `kb_list`, `kb_read` (especially wiki/memory.md) in the **department wiki**.\n"
                "- Use `web_search` (and `fetch_url` if needed) for current sources.\n"
                "- List **numbered** concrete topic hypotheses with brief rationale and source hints.\n"
                "- **Do not** create final pages with `kb_write` yet — only research and collect."
            ),
        ),
        (
            "CRITIC",
            (
                "You are the **critic** (phase 2).\n"
                "- Skeptically review the prior research: what is truly new vs. already in the wiki?\n"
                "- Are the approaches **specific** enough (no empty platitudes)?\n"
                "- What **gaps** remain (evidence, numbers, concrete next steps)?\n"
                "- Give a **numbered list** of points to investigate in the next research round."
            ),
        ),
        (
            "RESEARCHER",
            (
                "You are again the **research agent** (phase 3).\n"
                "- Address the **gaps** from the critique: targeted `kb_search`/`web_search`.\n"
                "- Refine or correct the topic list; drop weak points.\n"
                "- **Still no** final `kb_write` — only deepen content."
            ),
        ),
        (
            "CRITIC",
            (
                "You are the **critic** (phase 4).\n"
                "- Second **quality pass**: redundancies, contradictions, missing evidence?\n"
                "- Which topics are **ready** for a wiki page, which should be dropped?\n"
                "- Brief **priorities** (high/medium/low) per remaining topic."
            ),
        ),
        (
            "VALIDATOR",
            (
                "You are the **plausibility reviewer** (phase 5).\n"
                "- Check **relevance** to the project (memory/context) and **duplicates** against wiki content.\n"
                "- Keep only topics with **substance**; pick the **single strongest topic**.\n"
                "- List the **final topic** with title + 2–4 sentence summary (no tool calls)."
            ),
        ),
        (
            "RESEARCHER",
            (
                "You are the **research agent** (phase 6 — completion).\n\n"
                "**REQUIRED — call `kb_write`!**\n"
                "Create **exactly one** thorough wiki page on the final topic from phase 5:\n"
                "- Path: `wiki/wissen/...`, `wiki/ergebnisse/...`, `content/drafts/...` (as appropriate)\n"
                "- Metadata: `title`, `category`, `tags`, `job_role: deliverable`\n"
                "- Content: full, in-depth Markdown article (not just bullet points)\n"
                "- Optional: **one** additional `supporting` page if extensive source material exists\n\n"
                "Quality over quantity — one excellent page beats several shallow ones.\n\n"
                "If you make **no** `kb_write` call, the entire run was wasted.\n"
                "**After** the `kb_write` call: brief overall summary in natural language."
            ),
        ),
    ]


_PROACTIVE_ROLES: list[tuple[str, str]] = _proactive_role_prompts()
