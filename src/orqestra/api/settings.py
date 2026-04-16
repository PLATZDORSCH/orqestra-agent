"""UI and engine settings (e.g. display language)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from orqestra.api.constants import ROOT
from orqestra.api.state import check_auth, state
from orqestra.core.bootstrap import load_memory_prompt, save_config
from orqestra.core.localization import normalize_language
from orqestra.core.registry import update_orchestrator_persona_file

router = APIRouter()


class UiSettingsBody(BaseModel):
    language: str = Field(..., description="UI / template language: en or de")


@router.get("/api/settings/ui")
def get_ui_settings(request: Request) -> dict[str, str]:
    check_auth(request)
    eng = (state._cfg.get("engine") or {})
    lang = eng.get("language")
    if lang:
        return {"language": normalize_language(str(lang))}
    return {"language": "en"}


@router.put("/api/settings/ui")
def put_ui_settings(request: Request, body: UiSettingsBody) -> dict[str, str]:
    check_auth(request)
    lang = normalize_language(body.language)
    cfg = dict(state._cfg)
    eng = dict(cfg.get("engine") or {})
    eng["language"] = lang
    cfg["engine"] = eng
    save_config(cfg)
    state._cfg = cfg

    from orqestra.capabilities.skills import set_skill_read_language

    set_skill_read_language(lang)

    engine = state.engine
    engine._language = lang  # noqa: SLF001
    engine.reload_persona()

    kb_path = state.main_kb.base
    mp = load_memory_prompt(kb_path, cfg, language=lang)
    engine._memory_prompt = mp  # noqa: SLF001

    update_orchestrator_persona_file(state.registry, ROOT)

    return {"language": lang}
