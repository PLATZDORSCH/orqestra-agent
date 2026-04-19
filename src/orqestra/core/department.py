"""Single department: persona, wiki, skills, and shared capability registry."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from orqestra.capabilities.knowledge import KnowledgeBase
from orqestra.capabilities.skills import get_skills_summary_from
from orqestra.core.capabilities import Capability
from orqestra.core.engine import StrategyEngine
from orqestra.core.proactive_models import ProactiveConfig
from orqestra.core.research_budget import ResearchBudget

from orqestra.capabilities.research import web_search, fetch_url
from orqestra.capabilities.compute import run_script
from orqestra.capabilities.custom_code import write_code, list_code, read_code
from orqestra.capabilities.data import read_data
from orqestra.capabilities.charts import generate_chart

_OPTIONAL_CAPS: dict[str, Capability] = {}

try:
    from orqestra.capabilities.browser_seo import analyze_page_seo
    _OPTIONAL_CAPS["analyze_page_seo"] = analyze_page_seo
except ImportError:
    pass

try:
    from orqestra.capabilities.browser_axe import axe_wcag_scan
    _OPTIONAL_CAPS["axe_wcag_scan"] = axe_wcag_scan
except ImportError:
    pass

SHARED_CAPS: dict[str, Capability] = {
    "web_search": web_search,
    "fetch_url": fetch_url,
    "run_script": run_script,
    "write_code": write_code,
    "list_code": list_code,
    "read_code": read_code,
    "read_data": read_data,
    "generate_chart": generate_chart,
    **_OPTIONAL_CAPS,
}


def available_shared_capability_names() -> list[str]:
    """Names that may be assigned to a department (for API / builder UI)."""
    return sorted(SHARED_CAPS.keys())

# Which capabilities each department type gets (besides kb_* and skill_*)
DEPARTMENT_CAPABILITIES: dict[str, list[str]] = {

}


class Department:
    """A specialized sub-agent with its own knowledge base, skills, and persona."""

    def __init__(
        self,
        name: str,
        label: str,
        engine: StrategyEngine,
        kb: KnowledgeBase,
        skills_dir: Path,
        *,
        color: str | None = None,
        icon: str | None = None,
        proactive: ProactiveConfig | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self.engine = engine
        self.kb = kb
        self.skills_dir = skills_dir
        self.color = color
        self.icon = icon
        self.proactive = proactive
        self._capability_lock = threading.Lock()

    def run(
        self,
        task: str,
        *,
        history: list[dict] | None = None,
        stop_event: threading.Event | None = None,
        on_tool_call: Any | None = None,
        on_thinking: Any | None = None,
        job_context: dict | None = None,
        research_budget: ResearchBudget | None = None,
    ) -> str:
        return self.engine.run(
            task, history,
            stop_event=stop_event,
            on_tool_call=on_tool_call,
            on_thinking=on_thinking,
            job_context=job_context,
            research_budget=research_budget,
        )

    def search(self, query: str, limit: int = 5) -> list[dict]:
        results, _suggestions = self.kb.search(query, limit=limit)
        return results

    def skills_summary(self) -> list[dict]:
        return get_skills_summary_from(self.skills_dir)
