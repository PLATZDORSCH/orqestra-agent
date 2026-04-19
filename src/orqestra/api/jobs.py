"""Job listing, export, detail, reply, cancel/delete."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import frontmatter
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from orqestra.api.models import ReplyRequest
from orqestra.api.state import check_auth, state
from orqestra.core.departments import DepartmentJob
from orqestra.core.registry import MAIN_WIKI_JOB_DEPARTMENT

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/jobs")
def list_jobs(request: Request, offset: int = 0, limit: int = 20):
    """Paginated list of tracked jobs.

    Returns the full set sorted by `jobs_for_display` (running first, then by
    recency). `limit=0` returns everything starting at `offset`.
    """
    check_auth(request)
    jobs = state.registry.jobs_for_display()
    total = len(jobs)
    off = max(0, int(offset))
    lim = int(limit)
    if lim <= 0:
        sliced = jobs[off:]
    else:
        sliced = jobs[off : off + lim]
    items = [
        {
            "job_id": j.id,
            "department": j.department,
            "status": j.status(),
            "elapsed_seconds": round(j.elapsed_seconds(), 1),
            "task_preview": j.task[:200],
            "mode": j.mode,
            "pipeline_run_id": j.pipeline_run_id,
            "proactive_mission_id": j.proactive_mission_id,
            "proactive_mission_label": j.proactive_mission_label,
        }
        for j in sliced
    ]
    return {
        "jobs": items,
        "total": total,
        "offset": off,
        "limit": lim,
        "has_more": (off + len(items)) < total,
    }


@router.get("/api/jobs/export/trajectories")
def export_job_trajectories(
    request: Request,
    department: str | None = None,
    status: str = "done",
    limit: int = 500,
):
    """Export stored jobs as newline-delimited JSON (one trajectory per line)."""
    check_auth(request)
    store = state.registry.job_store
    if store is None:
        raise HTTPException(503, "Job store not configured")
    records = store.list_for_export(status=status, department=department, limit=limit)
    lines: list[str] = []
    for rec in records:
        messages: list[dict[str, Any]] = list(rec.get("history", []))
        messages.append({"role": "user", "content": rec["task"]})
        result = rec.get("result")
        err = rec.get("error")
        if result:
            messages.append({"role": "assistant", "content": result})
        elif err:
            messages.append({"role": "assistant", "content": f"[Fehler: {err}]"})
        else:
            messages.append({"role": "assistant", "content": ""})
        obj = {
            "messages": messages,
            "metadata": {
                "job_id": rec["id"],
                "department": rec["department"],
                "events": rec.get("events", []),
            },
        }
        lines.append(json.dumps(obj, ensure_ascii=False))
    body = "\n".join(lines)
    if body:
        body += "\n"
    return Response(content=body, media_type="application/x-ndjson")


def job_events_payload(job: DepartmentJob) -> list[dict]:
    """Live events from RAM, or persisted events from JobStore if RAM is empty."""
    if job.events:
        return [e.to_dict() for e in job.events]
    store = state.registry.job_store
    if store is not None:
        rec = store.get(job.id)
        if rec:
            ev = rec.get("events") or []
            return ev if isinstance(ev, list) else []
    return []


def _path_from_kb_write_event(ev: dict) -> str:
    """Resolve wiki path from kb_write event (detail, or JSON / regex fallback on preview)."""
    detail = ev.get("detail") or {}
    path = (detail.get("path") or "").strip()
    if path:
        return path
    if ev.get("name") not in ("kb_write", "my_kb_write"):
        return ""
    preview = (ev.get("preview") or "").strip()
    if preview.startswith("{"):
        try:
            parsed = json.loads(preview)
            if isinstance(parsed, dict):
                p = parsed.get("path")
                if isinstance(p, str) and p.strip():
                    return p.strip()
        except json.JSONDecodeError:
            pass
    # Truncated or partial JSON from the engine preview
    m = re.search(r'"path"\s*:\s*"([^"]+)"', preview)
    if m:
        return m.group(1).strip()
    return ""


def extract_written_files(job: DepartmentJob, registry: Any) -> list[dict]:
    """Extract written file paths from kb_write events; enrich title/job_role from disk frontmatter."""
    events = job_events_payload(job)
    seen: set[str] = set()
    files: list[dict] = []
    dept = registry.get(job.department) if registry is not None else None
    if dept is not None:
        kb_base = dept.kb.base
    elif job.department == MAIN_WIKI_JOB_DEPARTMENT:
        kb_base = state.main_kb.base
    else:
        kb_base = None

    for ev in events:
        name = ev.get("name")
        if name == "kb_write":
            kb_base_ev = kb_base
        elif name == "my_kb_write":
            kb_base_ev = getattr(state, "personal_kb", None)
            kb_base_ev = kb_base_ev.base if kb_base_ev is not None else None
        else:
            continue
        path = _path_from_kb_write_event(ev)
        if not path or path in seen:
            continue
        seen.add(path)
        title = path.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ").replace("_", " ").title()
        job_role: str | None = None
        if kb_base_ev is not None:
            full = kb_base_ev / path
            if full.is_file():
                try:
                    doc = frontmatter.load(str(full))
                    m = doc.metadata or {}
                    if m.get("title"):
                        title = str(m["title"])
                    jr = m.get("job_role")
                    if jr is not None:
                        job_role = str(jr).strip().lower() or None
                except Exception:
                    pass
        entry: dict[str, Any] = {"path": path, "title": title}
        if job_role:
            entry["job_role"] = job_role
        files.append(entry)
    return files


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    check_auth(request)
    job = state.registry.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Unknown job: {job_id}")
    result, err = job.result_or_error()
    written_files = extract_written_files(job, state.registry)
    if job.department == MAIN_WIKI_JOB_DEPARTMENT:
        written_files = []
    return {
        "job_id": job.id,
        "department": job.department,
        "status": job.status(),
        "elapsed_seconds": round(job.elapsed_seconds(), 1),
        "task": job.task,
        "result": result,
        "error": err,
        "history": job.history,
        "events": job_events_payload(job),
        "written_files": written_files,
        "mode": job.mode,
        "max_iterations": job.max_iterations,
        "current_iteration": job.current_iteration,
        "eval_status": job.eval_status,
        "progress_pct": job.progress_pct,
        "pipeline_run_id": job.pipeline_run_id,
        "proactive_mission_id": job.proactive_mission_id,
        "proactive_mission_label": job.proactive_mission_label,
    }


@router.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str, request: Request):
    """Re-run a failed or cancelled job with the original task."""
    check_auth(request)
    try:
        job = state.registry.retry_job(job_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return {
        "job_id": job.id,
        "department": job.department,
        "status": "running",
    }


@router.post("/api/jobs/{job_id}/reply")
def reply_to_job(job_id: str, body: ReplyRequest, request: Request):
    """Continue a finished job in-place (same job_id, conversation grows)."""
    check_auth(request)
    try:
        job = state.registry.reply_to_job(job_id, body.message)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return {
        "job_id": job.id,
        "department": job.department,
        "status": "running",
    }


@router.delete("/api/jobs/{job_id}")
def cancel_or_delete_job(job_id: str, request: Request):
    """Cancel a running job or permanently delete a finished/failed/cancelled job."""
    check_auth(request)
    job = state.registry.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Unknown job: {job_id}")
    if job._is_active():
        out = state.registry.cancel_job(job_id)
    else:
        out = state.registry.delete_job(job_id)
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@router.post("/api/proactive/trigger")
def trigger_proactive(request: Request):
    """Manually submit one proactive multi-phase job per department (respects department proactive flag)."""
    check_auth(request)
    from orqestra.core.scheduler import trigger_now

    count = trigger_now(state.registry)
    return {"triggered": count, "message": f"Submitted {count} proactive job(s)"}
