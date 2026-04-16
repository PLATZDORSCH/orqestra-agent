"""Department registry — facade: build departments, background jobs, orchestrator tools."""

from __future__ import annotations

from orqestra.core.registry_constants import (
    DEFAULT_DEPT_COLORS,
    MAIN_WIKI_JOB_DEPARTMENT,
    ORCHESTRATOR_DEPT_TOOL_NAMES,
)
from orqestra.core.registry_core import DepartmentRegistryCore
from orqestra.core.registry_delegate import DepartmentRegistryDelegateMixin
from orqestra.core.registry_jobs import DepartmentRegistryJobsMixin
from orqestra.core.registry_persona import (
    render_delegation_guidelines_markdown,
    render_departments_table_markdown,
    sync_orchestrator_department_tools,
    update_orchestrator_persona_file,
)
from orqestra.core.registry_yaml import load_departments_yaml, save_departments_yaml


class DepartmentRegistry(
    DepartmentRegistryCore,
    DepartmentRegistryJobsMixin,
    DepartmentRegistryDelegateMixin,
):
    """Builds and holds all departments; provides delegate + cross-search + async jobs."""


__all__ = [
    "DEFAULT_DEPT_COLORS",
    "DepartmentRegistry",
    "MAIN_WIKI_JOB_DEPARTMENT",
    "ORCHESTRATOR_DEPT_TOOL_NAMES",
    "load_departments_yaml",
    "render_delegation_guidelines_markdown",
    "render_departments_table_markdown",
    "save_departments_yaml",
    "sync_orchestrator_department_tools",
    "update_orchestrator_persona_file",
]
