"""Department system — re-exports for backward-compatible imports.

Implementation is split across:
  - core/department.py — Department, SHARED_CAPS
  - core/jobs.py — JobEvent, DepartmentJob
  - core/registry.py — DepartmentRegistry, YAML / persona helpers
  - core/deep_work.py — deep-work eval
  - core/proactive.py — proactive pipeline prompts
"""

from __future__ import annotations

from orqestra.core.department import (
    DEPARTMENT_CAPABILITIES,
    Department,
    SHARED_CAPS,
    available_shared_capability_names,
)
from orqestra.core.jobs import DepartmentJob, JobEvent
from orqestra.core.registry import (
    DepartmentRegistry,
    ORCHESTRATOR_DEPT_TOOL_NAMES,
    load_departments_yaml,
    render_delegation_guidelines_markdown,
    render_departments_table_markdown,
    save_departments_yaml,
    sync_orchestrator_department_tools,
    update_orchestrator_persona_file,
)

__all__ = [
    "DEPARTMENT_CAPABILITIES",
    "Department",
    "DepartmentJob",
    "DepartmentRegistry",
    "JobEvent",
    "ORCHESTRATOR_DEPT_TOOL_NAMES",
    "SHARED_CAPS",
    "available_shared_capability_names",
    "load_departments_yaml",
    "render_delegation_guidelines_markdown",
    "render_departments_table_markdown",
    "save_departments_yaml",
    "sync_orchestrator_department_tools",
    "update_orchestrator_persona_file",
]
