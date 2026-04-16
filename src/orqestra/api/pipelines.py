"""Orchestrator pipelines CRUD and runs."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from orqestra.api.constants import ROOT
from orqestra.api.language_utils import resolve_ui_language
from orqestra.api.models import PipelineUpsertRequest, StartPipelineRunRequest
from orqestra.api.state import check_auth, state
from orqestra.core.pipelines import (
    PipelineDef,
    PipelineStep,
    install_pipeline_template,
    list_pipeline_templates,
    sync_orchestrator_pipeline_tools,
    update_orchestrator_pipeline_file,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _refresh_orchestrator_pipeline_tools() -> None:
    sync_orchestrator_pipeline_tools(state.engine, state.pipeline_runner, state.registry)
    update_orchestrator_pipeline_file(state.pipeline_runner, ROOT)
    state.engine.invalidate_persona()


def _validate_departments(steps: list[PipelineStep]) -> None:
    names = set(state.registry.names())
    for s in steps:
        if s.department not in names:
            raise HTTPException(
                400,
                f"Unknown department: {s.department}. Available: {sorted(names)}",
            )


@router.get("/api/pipelines")
def list_pipelines(request: Request):
    check_auth(request)
    return {"pipelines": [p.to_dict() for p in state.pipeline_runner.pipelines]}


@router.get("/api/pipelines/{name}")
def get_pipeline(name: str, request: Request):
    check_auth(request)
    p = state.pipeline_runner.get_pipeline(name)
    if not p:
        raise HTTPException(404, f"Unknown pipeline: {name}")
    return p.to_dict()


@router.post("/api/pipelines")
def create_pipeline(body: PipelineUpsertRequest, request: Request):
    check_auth(request)
    if state.pipeline_runner.get_pipeline(body.name):
        raise HTTPException(409, f"Pipeline already exists: {body.name}")
    steps = [
        PipelineStep(
            department=s.department,
            task_template=s.task_template,
            result_key=s.result_key,
            mode=s.mode if s.mode in ("single", "deep", "proactive") else "deep",
        )
        for s in body.steps
    ]
    _validate_departments(steps)
    p = PipelineDef(
        name=body.name,
        label=body.label,
        description=body.description,
        steps=steps,
        variable_descriptions=dict(body.variable_descriptions),
    )
    state.pipeline_runner.upsert_pipeline(p)
    _refresh_orchestrator_pipeline_tools()
    return p.to_dict()


@router.put("/api/pipelines/{name}")
def update_pipeline(name: str, body: PipelineUpsertRequest, request: Request):
    check_auth(request)
    if body.name != name:
        raise HTTPException(400, "Body name must match URL name")
    steps = [
        PipelineStep(
            department=s.department,
            task_template=s.task_template,
            result_key=s.result_key,
            mode=s.mode if s.mode in ("single", "deep", "proactive") else "deep",
        )
        for s in body.steps
    ]
    _validate_departments(steps)
    p = PipelineDef(
        name=body.name,
        label=body.label,
        description=body.description,
        steps=steps,
        variable_descriptions=dict(body.variable_descriptions),
    )
    state.pipeline_runner.upsert_pipeline(p)
    _refresh_orchestrator_pipeline_tools()
    return p.to_dict()


@router.delete("/api/pipelines/{name}")
def delete_pipeline(name: str, request: Request):
    check_auth(request)
    if not state.pipeline_runner.delete_pipeline(name):
        raise HTTPException(404, f"Unknown pipeline: {name}")
    _refresh_orchestrator_pipeline_tools()
    return {"success": True, "name": name}


@router.get("/api/pipeline-templates")
def get_pipeline_templates(request: Request):
    check_auth(request)
    installed_names = {p.name for p in state.pipeline_runner.pipelines}
    templates = list_pipeline_templates()
    for tpl in templates:
        tpl["installed"] = tpl["name"] in installed_names
    return {"templates": templates}


@router.post("/api/pipeline-templates/{name}/install")
def install_pipeline_from_template(name: str, request: Request):
    check_auth(request)
    try:
        pdef = install_pipeline_template(
            name,
            state.pipeline_runner,
            language=resolve_ui_language(request),
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    dept_names = set(state.registry.names())
    missing = [s.department for s in pdef.steps if s.department not in dept_names]
    _refresh_orchestrator_pipeline_tools()
    return {
        "success": True,
        "pipeline": pdef.to_dict(),
        "missing_departments": missing,
    }


@router.post("/api/pipelines/{name}/run")
def start_pipeline_run(name: str, body: StartPipelineRunRequest, request: Request):
    check_auth(request)
    try:
        run = state.pipeline_runner.start_run(name, dict(body.variables))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "run_id": run.id,
        "pipeline": run.pipeline,
        "status": run.status,
        "current_step": run.current_step,
        "total_steps": len(run.step_states),
    }


@router.get("/api/pipeline-runs")
def list_pipeline_runs(request: Request, limit: int = 100):
    check_auth(request)
    runs = state.pipeline_runner.list_runs(limit=limit)
    return {
        "runs": [
            {
                "run_id": r.id,
                "pipeline": r.pipeline,
                "status": r.status,
                "current_step": r.current_step,
                "total_steps": len(r.step_states),
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "error": r.error,
            }
            for r in runs
        ],
    }


@router.get("/api/pipeline-runs/{run_id}")
def get_pipeline_run(run_id: str, request: Request):
    check_auth(request)
    run = state.pipeline_runner.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Unknown pipeline run: {run_id}")
    return {
        "run_id": run.id,
        "pipeline": run.pipeline,
        "status": run.status,
        "variables": run.variables,
        "current_step": run.current_step,
        "total_steps": len(run.step_states),
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error": run.error,
        "steps": [s.to_dict() for s in run.step_states],
    }


@router.post("/api/pipeline-runs/{run_id}/cancel")
def cancel_pipeline_run(run_id: str, request: Request):
    check_auth(request)
    out = state.pipeline_runner.cancel_run(run_id)
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@router.delete("/api/pipeline-runs/{run_id}")
def delete_pipeline_run(run_id: str, request: Request):
    check_auth(request)
    out = state.pipeline_runner.delete_run(run_id)
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out
