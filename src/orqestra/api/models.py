"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str


class OrchestratorChatJobRequest(BaseModel):
    """Start a department job from orchestrator chat context (LLM picks department)."""

    session_id: str
    mode: str = "deep"
    draft_message: str | None = None


class TaskRequest(BaseModel):
    task: str
    mode: str = "deep"


class ChatToJobRequest(BaseModel):
    """Chat turns from the department UI to formulate a background job task."""

    turns: list[dict[str, Any]]
    mode: str = "deep"
    draft_message: str | None = None


class DeptChatRequest(BaseModel):
    message: str


class ReplyRequest(BaseModel):
    message: str


class BuilderChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    step: str
    department_name: str | None = None
    department_label: str | None = None
    # Q&A step id when step == "suggestions": domain | tasks | style | knowledge
    qa_step: str | None = None
    # UI language: de | en (optional; falls back to X-Orqestra-Lang header or engine config)
    language: str | None = None


class SkillCreateItem(BaseModel):
    title: str
    description: str = ""
    content: str = ""


class SkillSuggestRequest(BaseModel):
    """Body for POST .../skills/suggest (optional; department context comes from URL)."""

    model_config = ConfigDict(extra="ignore")
    language: str | None = None


class SkillGenerateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    language: str | None = None


class SkillSaveRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    content: str = ""


class CreateDepartmentRequest(BaseModel):
    name: str
    label: str
    persona_content: str
    capabilities: list[str]
    skills: list[SkillCreateItem] = []


class SessionResponse(BaseModel):
    session_id: str


class PipelineStepModel(BaseModel):
    department: str = Field(..., min_length=1)
    task_template: str = Field(..., min_length=1)
    result_key: str | None = None
    mode: str = "deep"


class PipelineUpsertRequest(BaseModel):
    """Create or replace a pipeline definition."""

    name: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    description: str = ""
    steps: list[PipelineStepModel] = Field(default_factory=list)
    variable_descriptions: dict[str, str] = Field(default_factory=dict)


class StartPipelineRunRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


class MissionAPIModel(BaseModel):
    """One proactive mission template for a department."""

    id: str = Field(..., min_length=1)
    label: str = ""
    prompt: str = ""


class ProactiveConfigAPIModel(BaseModel):
    """Persisted under ``departments.yaml`` → ``proactive:``.

    ``enabled`` is opt-in: the user must explicitly turn it on per department.
    """

    enabled: bool = False
    schedule: str | None = None
    strategy: str = "rotate"
    missions: list[MissionAPIModel] = Field(default_factory=list)
