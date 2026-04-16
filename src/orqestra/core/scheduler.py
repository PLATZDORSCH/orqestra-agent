"""Proactive scheduler — triggers autonomous multi-phase jobs for departments.

Uses APScheduler (optional dependency). If not installed, the scheduler is silently disabled.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orqestra.core.departments import DepartmentRegistry

log = logging.getLogger(__name__)

_scheduler_instance = None


def _proactive_tick(registry: DepartmentRegistry) -> None:
    """Fired by the scheduler: submit one proactive job per department."""
    for name in registry.names():
        dept = registry.get(name)
        if dept is None:
            continue
        proactive_flag = getattr(dept, "proactive", True)
        if not proactive_flag:
            continue
        try:
            job = registry.submit_proactive_job(name)
            log.info("Proactive job submitted: %s (%s)", job.id, name)
        except Exception:
            log.exception("Failed to submit proactive job for %s", name)


def start_scheduler(
    registry: DepartmentRegistry,
    cron_expr: str = "0 6 * * *",
) -> bool:
    """Start the APScheduler with a cron trigger. Returns True if started."""
    global _scheduler_instance
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.info("APScheduler not installed — proactive scheduler disabled (pip install apscheduler)")
        return False

    if _scheduler_instance is not None:
        log.warning("Scheduler already running")
        return True

    parts = cron_expr.split()
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

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        _proactive_tick,
        trigger=trigger,
        args=[registry],
        id="proactive_pipeline",
        replace_existing=True,
    )
    sched.start()
    _scheduler_instance = sched
    log.info("Proactive scheduler started (cron: %s)", cron_expr)
    return True


def stop_scheduler() -> None:
    global _scheduler_instance
    if _scheduler_instance is not None:
        _scheduler_instance.shutdown(wait=False)
        _scheduler_instance = None
        log.info("Proactive scheduler stopped")


def trigger_now(registry: DepartmentRegistry) -> int:
    """Manually trigger proactive jobs for all departments. Returns number of jobs submitted."""
    count = 0
    for name in registry.names():
        dept = registry.get(name)
        if dept is None:
            continue
        try:
            registry.submit_proactive_job(name)
            count += 1
        except Exception:
            log.exception("Failed to trigger proactive job for %s", name)
    return count
