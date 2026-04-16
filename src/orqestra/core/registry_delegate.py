"""DepartmentRegistry mixin: orchestrator delegate / cross-search capabilities."""

from __future__ import annotations

import json
import logging
from typing import Any

from orqestra.core.capabilities import Capability

log = logging.getLogger(__name__)


class DepartmentRegistryDelegateMixin:
    """Capabilities for the orchestrator (delegate, cross-search, job polling)."""

    def delegate_background_json(
        self,
        dept_name: str,
        task: str,
        *,
        mode: str = "deep",
    ) -> str:
        """Start a department job in a worker thread; return JSON with job_id (never blocks the CLI)."""
        dept_names = self.names()
        if dept_name not in dept_names:
            return json.dumps(
                {"error": f"Unknown department: {dept_name}. Available: {dept_names}"},
                ensure_ascii=False,
            )
        log.info("Background delegate to '%s': %s", dept_name, task[:120])
        try:
            norm_mode = mode if mode in ("single", "deep", "proactive") else "single"
            job = self.submit_job(dept_name, task, mode=norm_mode)
            return json.dumps(
                {
                    "job_id": job.id,
                    "department": dept_name,
                    "status": "submitted",
                    "message": (
                        f"Background job {job.id} started (CLI stays responsive). "
                        f"Poll with check_job(job_id); user can use /status, /results, /stop in the terminal."
                    ),
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            log.exception("delegate background failed")
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)

    def create_delegate_capability(self) -> Capability:
        dept_names = self.names()

        def handle_delegate(args: dict) -> str:
            return self.delegate_background_json(
                args["department"],
                args["task"],
                mode="deep",
            )

        return Capability(
            name="delegate",
            description=(
                f"Send work to a specialized department in a **background thread** (does NOT block the user). "
                f"Jobs always run as **deep work** (multi-phase pipeline). "
                f"Returns a job_id immediately — the department runs SEO audits, analyses, etc. asynchronously. "
                f"Departments: {', '.join(dept_names)}. "
                f"Poll **check_job** with job_id until status is done, then read result. "
                f"Tell the user the job_id and that they can use /status and /results in the CLI."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "enum": dept_names,
                        "description": "Name of the department to delegate to",
                    },
                    "task": {
                        "type": "string",
                        "description": "Detailed task description for the department",
                    },
                },
                "required": ["department", "task"],
            },
            handler=handle_delegate,
        )

    def create_cross_search_capability(self) -> Capability:
        def handle_cross_search(args: dict) -> str:
            results = self.search_all(
                args["query"],
                limit=args.get("limit", 5),
            )
            return json.dumps(results, ensure_ascii=False)

        return Capability(
            name="cross_department_search",
            description=(
                "Search across ALL department knowledge bases at once. "
                "Returns results tagged with the originating department. "
                "Use this to find information that may live in any department's wiki."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term(s)"},
                    "limit": {"type": "integer", "description": "Max results per department (default: 5)"},
                },
                "required": ["query"],
            },
            handler=handle_cross_search,
        )

    def create_cross_read_capability(self) -> Capability:
        dept_names = ", ".join(sorted(self._departments))

        def handle_cross_read(args: dict) -> str:
            dept_name = args["department"]
            path = args["path"]
            dept = self.get(dept_name)
            if dept is None:
                return json.dumps(
                    {"error": f"Unknown department: {dept_name}",
                     "available": sorted(self._departments)},
                    ensure_ascii=False,
                )
            result = dept.kb.read(path)
            if "error" not in result:
                result["department"] = dept_name
            return json.dumps(result, ensure_ascii=False, default=str)

        return Capability(
            name="cross_department_read",
            description=(
                "Read a full wiki page from a specific department's knowledge base. "
                "Use **cross_department_search** first to discover pages, then read "
                "the full content here. "
                f"Available departments: {dept_names}"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": f"Department name — one of: {dept_names}",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relative path within the department KB (e.g. 'wiki/wissen/topic.md')",
                    },
                },
                "required": ["department", "path"],
            },
            handler=handle_cross_read,
        )

    def create_check_job_capability(self) -> Capability:
        def handle_check_job(args: dict) -> str:
            job_id = args["job_id"]
            job = self.get_job(job_id)
            if not job:
                return json.dumps({"error": f"Unknown job: {job_id}"}, ensure_ascii=False)

            st = job.status()
            out: dict[str, Any] = {
                "job_id": job.id,
                "department": job.department,
                "status": st,
                "elapsed_seconds": round(job.elapsed_seconds(), 1),
                "task_preview": job.task[:200] + ("…" if len(job.task) > 200 else ""),
            }
            result, err = job.result_or_error()
            if st in ("done", "cancelled"):
                out["result"] = result
            if st == "error" and err:
                out["error"] = err
            if st in ("pending", "running"):
                out["note"] = "Job still running — call check_job again later."
            return json.dumps(out, ensure_ascii=False)

        return Capability(
            name="check_job",
            description=(
                "Check status and result of a background department job started with **delegate**. "
                "Pass the job_id. When status is done, cancelled, or error, the result or error field is populated."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job id (e.g. seo-3)"},
                },
                "required": ["job_id"],
            },
            handler=handle_check_job,
        )

    def create_cancel_job_capability(self) -> Capability:
        def handle_cancel_job(args: dict) -> str:
            job_id = args["job_id"]
            return json.dumps(self.cancel_job(job_id), ensure_ascii=False)

        return Capability(
            name="cancel_job",
            description=(
                "Request cancellation of a running background job. "
                "Cooperative: the department stops after the current LLM round or tool call. "
                "Use the job_id returned by **delegate**."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job id to cancel"},
                },
                "required": ["job_id"],
            },
            handler=handle_cancel_job,
        )
