"""Proactive scheduler — per-department cron triggers for multi-phase jobs.

Uses APScheduler (optional dependency). If not installed, the scheduler is silently disabled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orqestra.core.departments import DepartmentRegistry

log = logging.getLogger(__name__)

_scheduler_instance = None


def _proactive_tick_for(registry: DepartmentRegistry, dept_name: str) -> None:
    """Submit proactive job(s) for one department (respects per-dept enabled + missions)."""
    from orqestra.core.proactive_models import effective_proactive

    dept = registry.get(dept_name)
    if dept is None:
        return
    if not effective_proactive(dept.proactive).enabled:
        return
    try:
        jobs = registry.submit_proactive_job(dept_name)
        for job in jobs:
            log.info("Proactive job submitted: %s (%s)", job.id, dept_name)
    except Exception:
        log.exception("Failed to submit proactive job for %s", dept_name)


def sync_department_schedules(
    registry: DepartmentRegistry,
    global_cron: str = "0 6 * * *",
) -> bool:
    """(Re)build one cron job per department. Call after startup or when YAML changes."""
    global _scheduler_instance
    if _scheduler_instance is None:
        return False
    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        return False

    from orqestra.core.proactive_models import effective_proactive

    _scheduler_instance.remove_all_jobs()
    for name in registry.names():
        dept = registry.get(name)
        if dept is None:
            continue
        cfg = effective_proactive(dept.proactive)
        if not cfg.enabled:
            continue
        cron = (cfg.schedule or "").strip() or global_cron
        parts = cron.split()
        if len(parts) == 5:
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            trigger = CronTrigger(hour=6)
        _scheduler_instance.add_job(
            _proactive_tick_for,
            trigger=trigger,
            args=[registry, name],
            id=f"proactive::{name}",
            replace_existing=True,
        )
    log.info("Proactive schedules synced (%d job(s))", len(_scheduler_instance.get_jobs()))
    return True


def start_scheduler(
    registry: DepartmentRegistry,
    cron_expr: str = "0 6 * * *",
) -> bool:
    """Start APScheduler and register per-department proactive jobs. *cron_expr* is the global fallback."""
    global _scheduler_instance
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.info("APScheduler not installed — proactive scheduler disabled (pip install apscheduler)")
        return False

    if _scheduler_instance is not None:
        sync_department_schedules(registry, cron_expr)
        return True

    sched = BackgroundScheduler(daemon=True)
    sched.start()
    _scheduler_instance = sched
    sync_department_schedules(registry, cron_expr)
    log.info("Proactive scheduler started (global fallback cron: %s)", cron_expr)
    return True


def stop_scheduler() -> None:
    global _scheduler_instance
    if _scheduler_instance is not None:
        _scheduler_instance.shutdown(wait=False)
        _scheduler_instance = None
        log.info("Proactive scheduler stopped")


def trigger_now(registry: DepartmentRegistry) -> int:
    """Manually trigger proactive jobs for all departments. Returns number of jobs submitted."""
    from orqestra.core.proactive_models import effective_proactive

    count = 0
    for name in registry.names():
        dept = registry.get(name)
        if dept is None:
            continue
        if not effective_proactive(dept.proactive).enabled:
            continue
        try:
            jobs = registry.submit_proactive_job(name)
            count += len(jobs)
        except Exception:
            log.exception("Failed to trigger proactive job for %s", name)
    return count
