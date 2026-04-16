"""DepartmentRegistry mixin: background jobs and persistence."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from orqestra.core.deep_work import (
    _DEEP_WORK_CONTEXT,
    deliverable_remediation_phase,
    has_deliverable_event,
    plan_roles,
)
from orqestra.core.department import Department
from orqestra.core.jobs import DepartmentJob, JobEvent
from orqestra.core.proactive import _PROACTIVE_CONTEXT, _PROACTIVE_PROMPT, _PROACTIVE_ROLES
from orqestra.core.registry_constants import (
    _FINISHED_JOB_MAX_AGE,
    _MAX_COMPLETED_JOBS,
    MAIN_WIKI_JOB_DEPARTMENT,
)

log = logging.getLogger(__name__)


class DepartmentRegistryJobsMixin:
    """Background jobs (ThreadPoolExecutor) and job store."""

    # ------------------------------------------------------------------
    # Background jobs (ThreadPoolExecutor)
    # ------------------------------------------------------------------

    def _run_proactive_pipeline(
        self,
        dept: Department,
        job: DepartmentJob,
        base_history: list[dict],
        stop_event: threading.Event,
    ) -> str:
        """Multi-phase proactive run: RESEARCHER / CRITIC / VALIDATOR; outputs via kb_write."""
        phases = _PROACTIVE_ROLES[: self._proactive_iterations]
        n = len(phases)
        history = list(base_history) if base_history else []
        last_result = ""
        cur_iteration = [0]

        for i, (role, role_template) in enumerate(phases, start=1):
            if stop_event.is_set():
                return "[Job cancelled by user]"
            job.current_iteration = i
            cur_iteration[0] = i
            self._persist_job(job)
            user_msg = f"[Phase {i}/{n} | {role}]\n\n{role_template}"
            if i == 1:
                user_msg = (
                    _PROACTIVE_CONTEXT.format(
                        department=dept.name,
                        label=dept.label,
                    )
                    + user_msg
                )

            def _on_tool(name: str, preview: str, fn_args: dict | None = None) -> None:
                detail = None
                if name == "kb_write" and fn_args:
                    path = fn_args.get("path", "")
                    meta = fn_args.get("metadata")
                    jr = None
                    if isinstance(meta, dict):
                        jr = meta.get("job_role")
                    if path:
                        detail = {"path": path}
                        if jr:
                            detail["job_role"] = jr
                job.events.append(JobEvent(
                    type="tool_call",
                    name=name,
                    preview=preview,
                    detail=detail,
                    iteration=cur_iteration[0],
                    role=role,
                ))

            def _on_think(label: str, preview: str = "") -> None:
                job.events.append(JobEvent(
                    type="thinking",
                    name=label,
                    preview=preview or "",
                    iteration=cur_iteration[0],
                    role=role,
                ))

            last_result = dept.run(
                user_msg,
                history=history if history else None,
                stop_event=stop_event,
                on_tool_call=_on_tool,
                on_thinking=_on_think,
                job_context={"job_id": job.id},
            )
            history = history + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": last_result},
            ]
        return last_result

    def _run_deep_pipeline(
        self,
        dept: Department,
        job: DepartmentJob,
        task: str,
        base_history: list[dict],
        stop_event: threading.Event,
    ) -> str:
        """Multi-phase deep work with LLM-planned roles (fallback: static RESEARCHER/CRITIC/VALIDATOR)."""
        phases = plan_roles(dept.engine, task, dept.name, dept.label)
        n_main = len(phases)
        job.max_iterations = n_main
        self._persist_job(job)

        history = list(base_history) if base_history else []
        last_result = ""
        cur_iteration = [0]

        def run_phase(i: int, n_total: int, role: str, role_template: str, prepend_context: bool) -> str:
            nonlocal last_result, history
            if stop_event.is_set():
                return last_result
            job.current_iteration = i
            cur_iteration[0] = i
            self._persist_job(job)

            user_msg = (
                f"[Phase {i}/{n_total} | {role}]\n\n{role_template}\n\n---\n\n**Auftrag:**\n{task}"
            )
            if prepend_context:
                user_msg = _DEEP_WORK_CONTEXT.format(department=dept.name, label=dept.label) + user_msg

            def _on_tool(name: str, preview: str, fn_args: dict | None = None) -> None:
                detail = None
                if name == "kb_write" and fn_args:
                    path = fn_args.get("path", "")
                    meta = fn_args.get("metadata")
                    jr = None
                    if isinstance(meta, dict):
                        jr = meta.get("job_role")
                    if path:
                        detail = {"path": path}
                        if jr:
                            detail["job_role"] = jr
                job.events.append(JobEvent(
                    type="tool_call",
                    name=name,
                    preview=preview,
                    detail=detail,
                    iteration=cur_iteration[0],
                    role=role,
                ))

            def _on_think(label: str, preview: str = "") -> None:
                job.events.append(JobEvent(
                    type="thinking",
                    name=label,
                    preview=preview or "",
                    iteration=cur_iteration[0],
                    role=role,
                ))

            last_result = dept.run(
                user_msg,
                history=history if history else None,
                stop_event=stop_event,
                on_tool_call=_on_tool,
                on_thinking=_on_think,
                job_context={"job_id": job.id},
            )
            history = history + [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": last_result},
            ]
            return last_result

        for idx, (role, role_template) in enumerate(phases, start=1):
            if stop_event.is_set():
                return "[Job cancelled by user]"
            last_result = run_phase(idx, n_main, role, role_template, prepend_context=(idx == 1))

        if not has_deliverable_event(job.events) and not stop_event.is_set():
            role, role_template = deliverable_remediation_phase()
            n_total = n_main + 1
            job.max_iterations = n_total
            self._persist_job(job)
            last_result = run_phase(n_total, n_total, role, role_template, prepend_context=False)

        if has_deliverable_event(job.events):
            job.eval_status = "GOAL_REACHED"
            job.progress_pct = 100
        else:
            job.eval_status = "CONTINUE"
            job.progress_pct = 90
        self._persist_job(job)
        return last_result

    def _run_job_worker(
        self,
        dept: Department,
        job: DepartmentJob,
        task: str,
        base_history: list[dict],
        stop_event: threading.Event,
    ) -> str:
        """Run one or more LLM rounds (deep mode: multi-phase RESEARCHER/CRITIC/VALIDATOR pipeline)."""
        mode = job.mode if job.mode in ("single", "deep", "proactive") else "single"
        if mode == "proactive":
            return self._run_proactive_pipeline(dept, job, base_history, stop_event)
        if mode == "deep":
            return self._run_deep_pipeline(dept, job, task, base_history, stop_event)

        # single mode — one shot
        history = list(base_history) if base_history else []
        if stop_event.is_set():
            return "[Job cancelled by user]"
        job.current_iteration = 1
        self._persist_job(job)
        cur_iteration = [1]

        def _on_tool_call_with_iter(name: str, preview: str, fn_args: dict | None = None) -> None:
            detail = None
            if name == "kb_write" and fn_args:
                path = fn_args.get("path", "")
                if path:
                    detail = {"path": path}
            job.events.append(JobEvent(
                type="tool_call", name=name, preview=preview,
                detail=detail, iteration=cur_iteration[0],
            ))

        def _on_thinking_with_iter(label: str, preview: str = "") -> None:
            job.events.append(JobEvent(
                type="thinking", name=label, preview=preview or "",
                iteration=cur_iteration[0],
            ))

        return dept.run(
            task,
            history=history if history else None,
            stop_event=stop_event,
            on_tool_call=_on_tool_call_with_iter,
            on_thinking=_on_thinking_with_iter,
            job_context={"job_id": job.id},
        )

    def _run_main_wiki_job_worker(
        self,
        job: DepartmentJob,
        task: str,
        base_history: list[dict],
        stop_event: threading.Event,
    ) -> str:
        """Single-shot orchestrator run for main-KB wiki ingest (same event shape as department jobs)."""
        from orqestra.api.state import state

        history = list(base_history) if base_history else []
        if stop_event.is_set():
            return "[Job cancelled by user]"
        job.current_iteration = 1
        self._persist_job(job)
        cur_iteration = [1]

        def _on_tool_call_with_iter(name: str, preview: str, fn_args: dict | None = None) -> None:
            detail = None
            if name in ("kb_write", "my_kb_write") and fn_args:
                path = fn_args.get("path", "")
                if path:
                    detail = {"path": path}
            job.events.append(JobEvent(
                type="tool_call", name=name, preview=preview,
                detail=detail, iteration=cur_iteration[0],
            ))

        def _on_thinking_with_iter(label: str, preview: str = "") -> None:
            job.events.append(JobEvent(
                type="thinking", name=label, preview=preview or "",
                iteration=cur_iteration[0],
            ))

        return state.engine.run(
            task,
            history if history else None,
            stop_event=stop_event,
            on_tool_call=_on_tool_call_with_iter,
            on_thinking=_on_thinking_with_iter,
            job_context={"job_id": job.id},
        )

    def submit_job(
        self,
        dept_name: str,
        task: str,
        *,
        history: list[dict] | None = None,
        mode: str = "deep",
        pipeline_run_id: str | None = None,
    ) -> DepartmentJob:
        """Run a department task in a worker thread; returns immediately with a job id."""
        self._ensure_executor()
        dept = self.get(dept_name)
        if dept is None:
            raise ValueError(f"Unknown department: {dept_name}")

        with self._lock:
            self._check_queue_capacity()
            self._job_counter += 1
            job_id = f"{dept_name}-{self._job_counter}"

        stop_event = threading.Event()
        job_history = list(history) if history else []
        norm_mode = mode if mode in ("single", "deep", "proactive") else "single"
        if norm_mode == "proactive":
            eff_max = min(len(_PROACTIVE_ROLES), self._proactive_iterations)
        elif norm_mode == "deep":
            eff_max = 8  # upper bound; actual phases (+ optional remediation) set in _run_deep_pipeline
        else:
            eff_max = 1

        job = DepartmentJob(
            id=job_id,
            department=dept_name,
            task=task,
            started_at=time.time(),
            history=job_history,
            future=None,
            stop_event=stop_event,
            mode=norm_mode,
            max_iterations=eff_max,
            current_iteration=0,
            pipeline_run_id=pipeline_run_id,
        )

        def _worker() -> str:
            try:
                return self._run_job_worker(
                    dept,
                    job,
                    task,
                    job_history,
                    stop_event,
                )
            finally:
                job.finished_at = time.time()

        assert self._executor is not None
        job.future = self._executor.submit(_worker)
        job.future.add_done_callback(lambda _fut: self._persist_job(job))

        with self._lock:
            self._jobs[job_id] = job
            self._prune_completed_locked()

        self._persist_job(job)
        log.info(
            "Submitted background job %s (%s)%s",
            job_id,
            dept_name[:40],
            f" pipeline_run={pipeline_run_id}" if pipeline_run_id else "",
        )
        return job

    def submit_main_wiki_ingest(self, task: str) -> DepartmentJob:
        """Run a task on the orchestrator engine (main knowledge base), e.g. wiki-ingest from uploads."""
        self._ensure_executor()
        with self._lock:
            self._check_queue_capacity()
            self._job_counter += 1
            job_id = f"main-wiki-{self._job_counter}"

        stop_event = threading.Event()
        job = DepartmentJob(
            id=job_id,
            department=MAIN_WIKI_JOB_DEPARTMENT,
            task=task,
            started_at=time.time(),
            history=[],
            future=None,
            stop_event=stop_event,
            mode="single",
            max_iterations=1,
            current_iteration=0,
        )

        def _worker() -> str:
            try:
                return self._run_main_wiki_job_worker(job, task, [], stop_event)
            finally:
                job.finished_at = time.time()

        assert self._executor is not None
        job.future = self._executor.submit(_worker)
        job.future.add_done_callback(lambda _fut: self._persist_job(job))

        with self._lock:
            self._jobs[job_id] = job
            self._prune_completed_locked()

        self._persist_job(job)
        log.info("Submitted main-wiki ingest job %s", job_id)
        return job

    def submit_proactive_job(self, dept_name: str) -> DepartmentJob:
        """Submit a proactive research job for a department."""
        task = _PROACTIVE_PROMPT.format(department=dept_name)
        return self.submit_job(
            dept_name,
            task,
            mode="proactive",
        )

    def reply_to_job(self, job_id: str, message: str) -> DepartmentJob:
        """Continue a finished job *in place* — the conversation grows, the job ID stays."""
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        if job._is_active():
            raise ValueError(f"Job {job_id} is still running — wait until it finishes before replying")

        if job.department == MAIN_WIKI_JOB_DEPARTMENT:
            raise ValueError("Reply is not supported for main wiki ingest jobs")

        dept = self.get(job.department)
        if dept is None:
            raise ValueError(f"Department not found: {job.department}")

        with self._lock:
            self._check_queue_capacity()

        # Append previous exchange to history
        result, err = job.result_or_error()
        job.history.append({"role": "user", "content": job.task})
        if result:
            job.history.append({"role": "assistant", "content": result})
        elif err:
            job.history.append({"role": "assistant", "content": f"[Fehler: {err}]"})

        # Update job for the new turn
        job.task = message
        job.finished_at = None
        job._stored_result = None
        job._stored_error = None
        job._stored_status = None
        stop_event = threading.Event()
        job.stop_event = stop_event

        history_snapshot = list(job.history)
        job.events = []
        job.current_iteration = 0

        def _worker() -> str:
            try:
                return self._run_job_worker(
                    dept,
                    job,
                    message,
                    history_snapshot,
                    stop_event,
                )
            finally:
                job.finished_at = time.time()

        self._ensure_executor()
        job.future = self._executor.submit(_worker)
        job.future.add_done_callback(lambda _fut: self._persist_job(job))

        self._persist_job(job)
        log.info("Replied to job %s (same ID, round %d)", job_id, len(job.history) // 2 + 1)
        return job

    def retry_job(self, job_id: str) -> DepartmentJob:
        """Re-run a failed or cancelled job with the same task and department.

        The history is preserved; the job re-enters the running state using the
        original task text. A fresh stop_event and Future are created.
        """
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        if job._is_active():
            raise RuntimeError(f"Job {job_id} is still running")

        if job.department == MAIN_WIKI_JOB_DEPARTMENT:
            raise ValueError("Retry is not supported for main wiki ingest jobs")

        dept = self.get(job.department)
        if dept is None:
            raise ValueError(f"Department not found: {job.department}")

        with self._lock:
            self._check_queue_capacity()

        # Reset run-time state, keep original task and history intact
        job.finished_at = None
        job._stored_result = None
        job._stored_error = None
        job._stored_status = None
        job.events = []
        job.current_iteration = 0
        job.eval_status = None
        job.progress_pct = 0
        stop_event = threading.Event()
        job.stop_event = stop_event

        task = job.task
        history_snapshot = list(job.history)

        def _worker() -> str:
            try:
                return self._run_job_worker(
                    dept,
                    job,
                    task,
                    history_snapshot,
                    stop_event,
                )
            finally:
                job.finished_at = time.time()

        self._ensure_executor()
        job.future = self._executor.submit(_worker)
        job.future.add_done_callback(lambda _fut: self._persist_job(job))

        self._persist_job(job)
        log.info("Retrying job %s (%s)", job_id, job.department)
        return job

    def _persist_job(self, job: DepartmentJob) -> None:
        """Write job state to the SQLite store (if attached)."""
        if self._job_store is None:
            return
        try:
            self._job_store.save(job.to_record())
        except Exception:
            log.debug("Failed to persist job %s", job.id, exc_info=True)

    def _prune_completed_locked(self) -> None:
        """Remove oldest completed jobs if we exceed the cap (caller must hold _lock)."""
        def _is_done_in_memory(j: DepartmentJob) -> bool:
            if j.future is None:
                return True  # historical / loaded from store — no live Future
            return j.future.done()

        completed = [(jid, j) for jid, j in self._jobs.items() if _is_done_in_memory(j)]
        if len(completed) <= _MAX_COMPLETED_JOBS:
            return
        completed.sort(key=lambda x: x[1].started_at)
        excess = len(completed) - _MAX_COMPLETED_JOBS
        for jid, _ in completed[:excess]:
            del self._jobs[jid]

    def get_job(self, job_id: str) -> DepartmentJob | None:
        return self._jobs.get(job_id)

    def delete_job(self, job_id: str) -> dict[str, Any]:
        """Permanently remove a finished/failed/cancelled job from memory and the store."""
        job = self._jobs.get(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        if job._is_active():
            return {"error": f"Job {job_id} is still running — cancel it first"}
        with self._lock:
            self._jobs.pop(job_id, None)
        if self._job_store is not None:
            self._job_store.delete(job_id)
        return {"success": True, "job_id": job_id}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Request cooperative cancellation of a running job."""
        job = self._jobs.get(job_id)
        if not job:
            return {"error": f"Unknown job: {job_id}"}
        if job.future is None:
            return {"error": f"Job {job_id} is not running"}
        if job.future.done():
            return {"error": f"Job {job_id} is already finished"}
        if job.stop_event is None:
            return {"error": f"Job {job_id} cannot be cancelled"}
        job.stop_event.set()
        return {"success": True, "job_id": job_id}

    def active_jobs(self) -> list[DepartmentJob]:
        return [j for j in self._jobs.values() if j.status() in ("pending", "running")]

    def recent_completed_jobs(self, limit: int = 20) -> list[DepartmentJob]:
        cutoff = time.time() - _FINISHED_JOB_MAX_AGE
        done = [
            j for j in self._jobs.values()
            if j.status() in ("done", "cancelled", "error")
            and (j.finished_at or j.started_at) >= cutoff
        ]
        done.sort(key=lambda x: x.started_at, reverse=True)
        return done[:limit]

    def shutdown(self, timeout: float = 10.0) -> None:
        """Cooperatively stop all running jobs and shut down the executor."""
        active = self.active_jobs()
        if active:
            log.info("Stopping %d active job(s)…", len(active))
            for job in active:
                if job.stop_event is not None:
                    job.stop_event.set()
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
            log.info("Executor shut down")

    def active_jobs_info(self) -> list[dict[str, str]]:
        """Lightweight dicts of active jobs — for context-window summaries."""
        return [
            {
                "job_id": j.id,
                "department": j.department,
                "task": j.task[:200],
                "status": j.status(),
            }
            for j in self.active_jobs()
        ]

    def jobs_for_display(self) -> list[DepartmentJob]:
        """All tracked jobs, running first, then by recency.

        Finished jobs older than 6 h are hidden.
        """
        cutoff = time.time() - _FINISHED_JOB_MAX_AGE
        jobs = [
            j for j in self._jobs.values()
            if j.status() in ("pending", "running")
            or (j.finished_at or j.started_at) >= cutoff
        ]
        jobs.sort(
            key=lambda j: (
                0 if j.status() in ("pending", "running") else 1,
                -j.started_at,
            ),
        )
        return jobs
