"""Orchestrator persona table / delegation blocks."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from orqestra.core.engine import StrategyEngine
from orqestra.core.registry_constants import (
    _DELEGATION_BEGIN,
    _DELEGATION_END,
    _DEPT_TABLE_BEGIN,
    _DEPT_TABLE_END,
    ORCHESTRATOR_DEPT_TOOL_NAMES,
)

log = logging.getLogger(__name__)


def sync_orchestrator_department_tools(engine: StrategyEngine, registry: Any) -> None:
    """Add or remove delegate / cross-search / job tools on the orchestrator engine."""
    mgr = engine.capabilities
    for name in ORCHESTRATOR_DEPT_TOOL_NAMES:
        mgr.remove(name)
    if len(registry) > 0:
        mgr.add(registry.create_delegate_capability())
        mgr.add(registry.create_cross_search_capability())
        mgr.add(registry.create_check_job_capability())
        mgr.add(registry.create_cancel_job_capability())
    engine.invalidate_tool_schema_cache()


def render_departments_table_markdown(registry: Any) -> str:
    if len(registry) == 0:
        return (
            "| Department | Expertise | Key tools |\n"
            "|---|---|---|\n"
            "| — | _No departments yet._ | Create some in the **web UI** (Department Builder) "
            "or add them in `departments.yaml`. |\n"
        )
    lines = ["| Department | Expertise | Key tools |", "|---|---|---|"]
    for name, dept in registry.items():
        tool_names = [
            n
            for n in dept.engine.capabilities.names()
            if not n.startswith("kb_") and not n.startswith("skill_")
        ]
        tools = ", ".join(f"`{n}`" for n in tool_names[:12])
        lines.append(f"| **{name}** | {dept.label} | {tools} |")
    return "\n".join(lines) + "\n"


def render_delegation_guidelines_markdown(registry: Any) -> str:
    if len(registry) == 0:
        return (
            "_As long as no departments exist, you **cannot** delegate. "
            "Ask the user to create a department in the web UI first._\n"
        )
    out = []
    for name, dept in registry.items():
        out.append(f"- Tasks and topics for **{dept.label}** → **`{name}`** (`delegate`)")
    out.append("")
    out.append(
        "When delegating, be **specific** in your task description. Include all context the "
        "department needs (URLs, company names, constraints, desired output format)."
    )
    return "\n".join(out) + "\n"


def _apply_orchestrator_dept_delegation_blocks(
    text: str,
    table_block: str,
    deleg_block: str,
    path_label: str,
) -> str:
    if _DEPT_TABLE_BEGIN in text and _DEPT_TABLE_END in text:
        text = re.sub(
            re.escape(_DEPT_TABLE_BEGIN) + r"[\s\S]*?" + re.escape(_DEPT_TABLE_END),
            table_block,
            text,
            count=1,
        )
    else:
        log.warning("%s missing ORQESTRA_DEPT_TABLE markers — skipping table update", path_label)

    if _DELEGATION_BEGIN in text and _DELEGATION_END in text:
        text = re.sub(
            re.escape(_DELEGATION_BEGIN) + r"[\s\S]*?" + re.escape(_DELEGATION_END),
            deleg_block,
            text,
            count=1,
        )
    else:
        log.warning("%s missing ORQESTRA_DELEGATION markers — skipping delegation update", path_label)

    return text


def update_orchestrator_persona_file(registry: Any, root: Path) -> None:
    """Rewrite the dynamic department table + delegation section in orchestrator persona files."""
    table_block = f"{_DEPT_TABLE_BEGIN}\n{render_departments_table_markdown(registry)}{_DEPT_TABLE_END}"
    deleg_block = f"{_DELEGATION_BEGIN}\n{render_delegation_guidelines_markdown(registry)}{_DELEGATION_END}"

    for rel in ("personas/orchestrator.md", "personas/orchestrator.de.md"):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        text = _apply_orchestrator_dept_delegation_blocks(text, table_block, deleg_block, rel)
        path.write_text(text, encoding="utf-8")


__all__ = [
    "render_delegation_guidelines_markdown",
    "render_departments_table_markdown",
    "sync_orchestrator_department_tools",
    "update_orchestrator_persona_file",
]
