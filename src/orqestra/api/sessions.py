"""Sessions and file upload."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from orqestra.api.models import SessionResponse
from orqestra.api.state import WebSession, check_auth, state
from orqestra.capabilities.files import process_upload

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/sessions", response_model=SessionResponse)
def create_session(request: Request):
    check_auth(request)
    state.prune_stale()
    s = WebSession()
    state.sessions[s.id] = s
    return SessionResponse(session_id=s.id)


@router.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, request: Request):
    check_auth(request)
    if session_id in state.sessions:
        del state.sessions[session_id]
    return {"ok": True}


@router.post("/api/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
):
    """Upload a document or image; returns extracted text or vision description."""
    check_auth(request)
    if session_id is not None:
        state.get_or_create_session(session_id)

    filename = file.filename or "upload"
    suffix = Path(filename).suffix

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)

    try:
        content = await file.read()
        tmp_path.write_bytes(content)
        result = process_upload(
            tmp_path,
            file.content_type,
            filename,
            state.engine.llm,
            state.engine.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "filename": result.filename,
        "mime": result.mime,
        "is_image": result.is_image,
        "context_text": result.context_text,
    }
