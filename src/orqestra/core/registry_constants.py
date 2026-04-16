"""Shared constants for the department registry."""

from __future__ import annotations

_MAX_COMPLETED_JOBS = 50
_FINISHED_JOB_MAX_AGE = 6 * 3600  # seconds — hide finished jobs older than this

# Default accent per department when `color` is omitted in departments.yaml (UI / topology).
DEFAULT_DEPT_COLORS = (
    "#6366f1",
    "#f59e0b",
    "#10b981",
    "#ef4444",
    "#8b5cf6",
    "#ec4899",
)

# Background jobs that run the orchestrator engine on the main KB (wiki ingest from API).
MAIN_WIKI_JOB_DEPARTMENT = "main_wiki"

ORCHESTRATOR_DEPT_TOOL_NAMES = (
    "delegate",
    "cross_department_search",
    "cross_department_read",
    "check_job",
    "cancel_job",
)

_DEPT_TABLE_BEGIN = "<!-- ORQESTRA_DEPT_TABLE_BEGIN -->"
_DEPT_TABLE_END = "<!-- ORQESTRA_DEPT_TABLE_END -->"
_DELEGATION_BEGIN = "<!-- ORQESTRA_DELEGATION_BEGIN -->"
_DELEGATION_END = "<!-- ORQESTRA_DELEGATION_END -->"

__all__ = [
    "_DELEGATION_BEGIN",
    "_DELEGATION_END",
    "_DEPT_TABLE_BEGIN",
    "_DEPT_TABLE_END",
    "_FINISHED_JOB_MAX_AGE",
    "_MAX_COMPLETED_JOBS",
    "DEFAULT_DEPT_COLORS",
    "MAIN_WIKI_JOB_DEPARTMENT",
    "ORCHESTRATOR_DEPT_TOOL_NAMES",
]
