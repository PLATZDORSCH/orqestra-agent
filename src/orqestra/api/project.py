"""API routes for project context (project.yaml)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from orqestra.api.state import check_auth
from orqestra.core.bootstrap import load_project, save_project, PROJECT_FIELDS

router = APIRouter()


class ProjectData(BaseModel):
    name: str = ""
    type: str = ""
    location: str = ""
    focus: str = ""
    target_market: str = ""
    notes: str = ""

    @property
    def is_configured(self) -> bool:
        return any(getattr(self, f) for f in PROJECT_FIELDS)


class ProjectResponse(ProjectData):
    configured: bool = False


@router.get("/api/project")
async def get_project(request: Request) -> ProjectResponse:
    check_auth(request)
    data = load_project()
    proj = ProjectData(**{k: data.get(k, "") for k in PROJECT_FIELDS})
    return ProjectResponse(**proj.model_dump(), configured=proj.is_configured)


@router.put("/api/project")
async def put_project(request: Request, body: ProjectData) -> ProjectResponse:
    check_auth(request)
    save_project(body.model_dump())
    return ProjectResponse(**body.model_dump(), configured=body.is_configured)
