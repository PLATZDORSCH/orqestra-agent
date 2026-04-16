"""Main chat and department chat (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from orqestra.api.models import ChatRequest, DeptChatRequest, OrchestratorChatJobRequest
from orqestra.api.state import check_auth, state
from orqestra.core.deep_work import formulate_orchestrator_job
from orqestra.core.engine import StrategyEngine

log = logging.getLogger(__name__)

router = APIRouter()


async def engine_sse_event_stream(
    engine: StrategyEngine,
    message: str,
    history: list[dict],
    *,
    log_exc_label: str = "engine.run failed",
) -> AsyncIterator[dict]:
    """Yield SSE event dicts for EventSourceResponse (tool_call, thinking, error, answer)."""
    progress_q: queue.Queue[tuple[str, str, str]] = queue.Queue()

    def _on_tool_call(name: str, preview: str, fn_args: dict | None = None) -> None:
        progress_q.put(("tool_call", name, preview))

    def _on_thinking(label: str, preview: str = "") -> None:
        progress_q.put(("thinking", label, preview))

    engine_task = asyncio.ensure_future(
        asyncio.to_thread(
            engine.run,
            message,
            history,
            on_tool_call=_on_tool_call,
            on_thinking=_on_thinking,
        )
    )

    while not engine_task.done():
        try:
            while True:
                kind, name, preview = progress_q.get_nowait()
                yield {
                    "event": kind,
                    "data": json.dumps({"name": name, "preview": preview}, ensure_ascii=False),
                }
        except queue.Empty:
            pass
        await asyncio.sleep(0.5)

    try:
        while True:
            kind, name, preview = progress_q.get_nowait()
            yield {
                "event": kind,
                "data": json.dumps({"name": name, "preview": preview}, ensure_ascii=False),
            }
    except queue.Empty:
        pass

    try:
        answer = engine_task.result()
    except Exception as exc:
        log.exception(log_exc_label)
        yield {
            "event": "error",
            "data": json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
        }
        return

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    yield {
        "event": "answer",
        "data": json.dumps({"content": answer}, ensure_ascii=False),
    }


@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    check_auth(request)
    session = state.get_or_create_session(body.session_id)

    active_jobs = state.registry.active_jobs_info() if len(state.registry) > 0 else None
    session.history = state.engine.summarize_if_needed(session.history, active_jobs=active_jobs)

    async def event_stream():
        async for ev in engine_sse_event_stream(
            state.engine,
            body.message,
            session.history,
            log_exc_label="engine.run failed",
        ):
            yield ev

    return EventSourceResponse(event_stream())


@router.post("/api/chat/job")
def create_orchestrator_chat_job(body: OrchestratorChatJobRequest, request: Request):
    """Pick a department from orchestrator chat context (LLM) and submit a background job."""
    check_auth(request)
    if len(state.registry) == 0:
        raise HTTPException(
            400,
            "Keine Departments vorhanden — lege zuerst eine Abteilung an.",
        )
    session = state.get_or_create_session(body.session_id)
    norm_mode = body.mode if body.mode in ("single", "deep") else "deep"

    department_options = [(name, dept.label) for name, dept in state.registry.items()]
    try:
        dept_name, task, summary = formulate_orchestrator_job(
            state.engine,
            department_options=department_options,
            history=list(session.history),
            draft_message=body.draft_message,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as exc:
        log.exception("formulate_orchestrator_job failed")
        raise HTTPException(502, f"Aufgabe konnte nicht geplant werden: {exc}") from exc

    try:
        job = state.registry.submit_job(dept_name, task, mode=norm_mode)
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e

    return {
        "job_id": job.id,
        "department": dept_name,
        "task_summary": summary,
        "status": "submitted",
    }


@router.post("/api/departments/{name}/chat")
async def dept_chat(name: str, body: DeptChatRequest, request: Request):
    """Conversational chat with a department engine (SSE, like the main chat)."""
    check_auth(request)
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}. Available: {state.registry.names()}")

    history = state.dept_chat_histories.setdefault(name, [])
    history = dept.engine.summarize_if_needed(history)
    state.dept_chat_histories[name] = history

    async def event_stream():
        async for ev in engine_sse_event_stream(
            dept.engine,
            body.message,
            history,
            log_exc_label="dept engine.run failed",
        ):
            yield ev

    return EventSourceResponse(event_stream())
