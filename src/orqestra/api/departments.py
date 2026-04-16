"""Departments CRUD, builder chat, capabilities, skills."""

from __future__ import annotations

import logging
import shutil

from fastapi import APIRouter, HTTPException, Request

from orqestra.api.constants import ROOT
from orqestra.api.language_utils import resolve_ui_language
from orqestra.api.models import (
    BuilderChatRequest,
    ChatToJobRequest,
    CreateDepartmentRequest,
    SkillGenerateRequest,
    SkillSaveRequest,
    SkillSuggestRequest,
    TaskRequest,
)
from orqestra.api.state import check_auth, state, sync_orchestrator_pipeline_artifacts
from orqestra.api.wiki import sync_department_links
from orqestra.core.deep_work import formulate_job_task_from_chat
from orqestra.core.department_builder import (
    BUILDER_STEP_PROMPTS_EN,
    SkillDraft,
    create_department_from_builder,
    generate_skill_content,
    run_builder_chat_llm,
    save_skill_draft_to_directory,
    suggest_skills_for_department,
)
from orqestra.core.departments import (
    available_shared_capability_names,
    load_departments_yaml,
    save_departments_yaml,
    sync_orchestrator_department_tools,
    update_orchestrator_persona_file,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/capabilities")
def list_capabilities(request: Request):
    check_auth(request)
    return {"capabilities": available_shared_capability_names()}


@router.post("/api/departments/builder/chat")
def builder_chat(body: BuilderChatRequest, request: Request):
    """LLM-gestützter Dialog für den Department Builder."""
    check_auth(request)
    if body.step not in BUILDER_STEP_PROMPTS_EN:
        raise HTTPException(400, f"Unknown step: {body.step}")

    try:
        return run_builder_chat_llm(
            state.engine,
            step=body.step,
            messages=body.messages,
            department_name=body.department_name,
            department_label=body.department_label,
            qa_step=body.qa_step,
            language=resolve_ui_language(request, body.language),
        )
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        log.exception("builder_chat LLM failed")
        raise HTTPException(502, f"LLM error: {exc}") from exc


@router.post("/api/departments")
def create_department_api(body: CreateDepartmentRequest, request: Request):
    check_auth(request)
    skills = [
        SkillDraft(title=sk.title, description=sk.description, content=sk.content)
        for sk in body.skills
    ]
    try:
        result = create_department_from_builder(
            root=ROOT,
            registry=state.registry,
            engine=state.engine,
            cfg=state._cfg,
            name=body.name,
            label=body.label,
            persona_content=body.persona_content,
            capabilities=body.capabilities,
            skills=skills,
        )
        sync_department_links()
        state.main_kb.refresh_navigation_pages()
        sync_orchestrator_pipeline_artifacts()
        return result
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/api/departments/{name}")
def delete_department_api(name: str, request: Request):
    check_auth(request)
    name = name.strip().lower()
    if not state.registry.get(name):
        raise HTTPException(404, f"Unbekanntes Department: {name}")

    for j in state.registry.jobs_for_display():
        if j.department == name and j.status() in ("pending", "running"):
            raise HTTPException(400, "Beende oder warte zuerst laufende Jobs dieses Departments.")

    rows = [r for r in load_departments_yaml(ROOT) if r.get("name") != name]
    save_departments_yaml(ROOT, rows)

    state.registry.remove_department(name)
    if name in state.dept_chat_histories:
        del state.dept_chat_histories[name]

    dept_path = ROOT / "departments" / name
    if dept_path.is_dir():
        try:
            shutil.rmtree(dept_path)
        except OSError as exc:
            log.warning("Could not remove department folder %s: %s", dept_path, exc)

    update_orchestrator_persona_file(state.registry, ROOT)
    sync_orchestrator_department_tools(state.engine, state.registry)
    sync_orchestrator_pipeline_artifacts()
    sync_department_links()
    state.main_kb.refresh_navigation_pages()

    return {"ok": True, "deleted": name}


@router.get("/api/departments")
def list_departments(request: Request):
    check_auth(request)
    out = []
    for name, dept in state.registry.items():
        out.append({
            "name": name,
            "label": dept.label,
            "color": dept.color,
            "icon": dept.icon,
            "capabilities": dept.engine.capabilities.names(),
            "skills": dept.skills_summary(),
        })
    return out


@router.get("/api/topology")
def topology(request: Request):
    """Graph data for Overview: orchestrator + departments + active job counts."""
    check_auth(request)
    departments = []
    for name, dept in state.registry.items():
        active_jobs = sum(
            1
            for j in state.registry.jobs_for_display()
            if j.department == name and j.status() in ("running", "pending")
        )
        departments.append({
            "id": name,
            "label": dept.label,
            "color": dept.color,
            "icon": dept.icon,
            "skills_count": len(dept.skills_summary()),
            "active_jobs": active_jobs,
        })
    return {
        "orchestrator": {"id": "orchestrator", "label": "Orqestra"},
        "departments": departments,
    }


def _read_department_persona(name: str) -> str:
    persona_path = ROOT / "departments" / name / "persona.md"
    if not persona_path.is_file():
        return ""
    return persona_path.read_text(encoding="utf-8")


@router.post("/api/departments/{name}/skills/suggest")
def suggest_skills_for_department_api(
    name: str,
    body: SkillSuggestRequest,
    request: Request,
):
    """LLM: skill ideas (title + short description) for the Skill Builder wizard."""
    check_auth(request)
    name = name.strip().lower()
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}")
    persona_text = _read_department_persona(name)
    if not persona_text.strip():
        raise HTTPException(400, "Department-Persona nicht lesbar.")
    existing_titles: list[str] = []
    for s in dept.skills_summary():
        t = s.get("title") or s.get("name")
        if isinstance(t, str) and t.strip():
            existing_titles.append(t.strip())
    try:
        items = suggest_skills_for_department(
            state.engine,
            persona_text=persona_text,
            department_label=dept.label,
            department_name=name,
            existing_skill_titles=existing_titles,
            language=resolve_ui_language(request, body.language),
        )
    except Exception as exc:
        log.exception("suggest_skills LLM failed")
        raise HTTPException(502, f"LLM error: {exc}") from exc
    return {"suggested_skills": items}


@router.post("/api/departments/{name}/skills/generate")
def generate_skill_api(name: str, body: SkillGenerateRequest, request: Request):
    """LLM: full skill draft (title, description, markdown content)."""
    check_auth(request)
    name = name.strip().lower()
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}")
    persona_text = _read_department_persona(name)
    if not persona_text.strip():
        raise HTTPException(400, "Department-Persona nicht lesbar.")
    try:
        draft = generate_skill_content(
            state.engine,
            persona_text=persona_text,
            department_label=dept.label,
            department_name=name,
            title=body.title.strip(),
            description=(body.description or "").strip(),
            language=resolve_ui_language(request, body.language),
        )
    except ValueError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        log.exception("generate_skill LLM failed")
        raise HTTPException(502, f"LLM error: {exc}") from exc
    return {
        "title": draft.title,
        "description": draft.description,
        "content": draft.content,
    }


@router.post("/api/departments/{name}/skills")
def save_skill_api(name: str, body: SkillSaveRequest, request: Request):
    """Persist a skill as ``.md`` in the department skills directory."""
    check_auth(request)
    name = name.strip().lower()
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}")
    sk = SkillDraft(
        title=body.title.strip(),
        description=(body.description or "").strip(),
        content=(body.content or "").strip(),
    )
    if not sk.title:
        raise HTTPException(400, "Titel fehlt.")
    if not sk.content.strip():
        raise HTTPException(400, "Inhalt fehlt.")
    try:
        fn = save_skill_draft_to_directory(
            dept.skills_dir,
            name,
            sk,
            tags=[name, "skill-builder"],
        )
    except OSError as exc:
        raise HTTPException(500, f"Skill konnte nicht gespeichert werden: {exc}") from exc
    return {"success": True, "filename": fn}


@router.delete("/api/departments/{name}/skills/{filename:path}")
def delete_skill(name: str, filename: str, request: Request):
    """Delete a skill file from a department's skills directory."""
    check_auth(request)
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}")
    if not filename.endswith(".md"):
        filename += ".md"
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(400, "Invalid filename")
    skill_path = dept.skills_dir / filename
    if not skill_path.resolve().is_relative_to(dept.skills_dir.resolve()):
        raise HTTPException(400, "Path escapes skills directory")
    if not skill_path.is_file():
        raise HTTPException(404, f"Skill not found: {filename}")
    skill_path.unlink()
    return {"success": True, "deleted": filename}


@router.post("/api/departments/{name}/jobs")
def create_department_job(name: str, body: TaskRequest, request: Request):
    check_auth(request)
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}. Available: {state.registry.names()}")
    try:
        job = state.registry.submit_job(
            name,
            body.task,
            mode=body.mode,
        )
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return {
        "job_id": job.id,
        "department": name,
        "status": "submitted",
    }


@router.post("/api/departments/{name}/jobs/from-chat")
def create_department_job_from_chat(name: str, body: ChatToJobRequest, request: Request):
    """Formulate a task from chat turns via LLM, then submit a deep-work job."""
    check_auth(request)
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}. Available: {state.registry.names()}")
    if not body.turns:
        raise HTTPException(400, "Mindestens ein Chat-Turn erforderlich.")
    try:
        task, task_summary = formulate_job_task_from_chat(
            dept.engine,
            department_label=dept.label,
            turns=body.turns,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as exc:
        log.exception("formulate_job_task_from_chat failed")
        raise HTTPException(502, f"Aufgabe konnte nicht formuliert werden: {exc}") from exc
    try:
        job = state.registry.submit_job(name, task, mode=body.mode)
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return {
        "job_id": job.id,
        "department": name,
        "task_summary": task_summary,
        "status": "submitted",
    }


@router.post("/api/departments/{name}/proactive")
def trigger_department_proactive(name: str, request: Request):
    """Submit a multi-phase proactive job for one department (autonomous topic research + kb_write)."""
    check_auth(request)
    dept = state.registry.get(name)
    if not dept:
        raise HTTPException(404, f"Unknown department: {name}. Available: {state.registry.names()}")
    try:
        job = state.registry.submit_proactive_job(name)
    except RuntimeError as e:
        raise HTTPException(429, str(e)) from e
    return {
        "job_id": job.id,
        "department": name,
        "status": "submitted",
    }


@router.get("/api/templates")
def list_templates_api(request: Request):
    check_auth(request)
    from orqestra.core.department_builder import list_templates

    return list_templates()


@router.post("/api/templates/{name}/install")
def install_template_api(name: str, request: Request):
    check_auth(request)
    from orqestra.core.department_builder import install_template

    try:
        result = install_template(
            name,
            root=ROOT,
            registry=state.registry,
            engine=state.engine,
            cfg=state._cfg,
            language=resolve_ui_language(request),
        )
        sync_department_links()
        state.main_kb.refresh_navigation_pages()
        sync_orchestrator_pipeline_artifacts()
        return result
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
