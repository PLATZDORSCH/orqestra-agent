"""Shared UI language resolution for API routes."""

from __future__ import annotations

from fastapi import Request

from orqestra.api.state import state
from orqestra.core.localization import normalize_language


def resolve_ui_language(request: Request, body_lang: str | None = None) -> str:
    """Prefer body language, then X-Orqestra-Lang header, then engine config; default en."""
    if body_lang:
        return normalize_language(body_lang)
    h = request.headers.get("X-Orqestra-Lang") or request.headers.get("x-orqestra-lang")
    if h:
        return normalize_language(h)
    cfg = getattr(state, "_cfg", None) or {}
    eng = cfg.get("engine") or {}
    if eng.get("language"):
        return normalize_language(str(eng["language"]))
    return "en"
