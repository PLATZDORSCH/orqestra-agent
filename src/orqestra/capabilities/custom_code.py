"""Persistent code storage — write, read, and list files in custom_code/<project>/.

Allows the agent to save scripts, tools, and programs that users request.
All file operations are sandboxed to the custom_code/ directory via path
validation — the agent cannot escape this folder.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from orqestra._paths import REPO_ROOT
from orqestra.core.capabilities import Capability

log = logging.getLogger(__name__)

CUSTOM_CODE_DIR = REPO_ROOT / "custom_code"

_MAX_READ_BYTES = 512_000  # 500 KB


def _resolve_safe_path(project: str, filename: str = "") -> Path:
    """Resolve a path inside custom_code/<project>/ and reject traversal attempts."""
    safe_project = re.sub(r"[^a-zA-Z0-9_\-]", "-", project.strip())
    if not safe_project:
        raise ValueError("project name is required")

    if filename:
        target = (CUSTOM_CODE_DIR / safe_project / filename).resolve()
    else:
        target = (CUSTOM_CODE_DIR / safe_project).resolve()

    anchor = str(CUSTOM_CODE_DIR.resolve()) + os.sep
    if not (str(target) + os.sep).startswith(anchor) and target != CUSTOM_CODE_DIR.resolve():
        raise ValueError("path escapes custom_code directory")

    return target


# ---------------------------------------------------------------------------
# write_code
# ---------------------------------------------------------------------------

def _handle_write_code(args: dict) -> str:
    project = args.get("project", "").strip()
    filename = args.get("filename", "").strip()
    content = args.get("content", "")

    if not project:
        return json.dumps({"error": "parameter 'project' is required"}, ensure_ascii=False)
    if not filename:
        return json.dumps({"error": "parameter 'filename' is required"}, ensure_ascii=False)

    try:
        target = _resolve_safe_path(project, filename)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        rel = target.relative_to(CUSTOM_CODE_DIR.resolve())
        log.info("write_code: %s (%d bytes)", rel, len(content))
        return json.dumps({
            "success": True,
            "path": str(rel),
            "size_bytes": len(content.encode("utf-8")),
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


write_code = Capability(
    name="write_code",
    description=(
        "Save a code file persistently to custom_code/<project>/<filename>. "
        "Use this when the user asks you to write a script, tool, or program. "
        "Each project gets its own subfolder. Supports any file type "
        "(Python, JSON, YAML, HTML, shell scripts, etc.). "
        "Subdirectories within the project are allowed (e.g. filename='src/utils.py')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project folder name (e.g. 'kunden-analyse', 'seo-report-tool')",
            },
            "filename": {
                "type": "string",
                "description": "File name within the project folder (e.g. 'main.py', 'config.json', 'src/utils.py')",
            },
            "content": {
                "type": "string",
                "description": "Full file content to write",
            },
        },
        "required": ["project", "filename", "content"],
    },
    handler=_handle_write_code,
)


# ---------------------------------------------------------------------------
# list_code
# ---------------------------------------------------------------------------

def _handle_list_code(args: dict) -> str:
    project = args.get("project", "").strip()

    base = CUSTOM_CODE_DIR.resolve()
    if not base.is_dir():
        return json.dumps({"projects": []}, ensure_ascii=False)

    if not project:
        projects = sorted(
            d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")
        )
        return json.dumps({"projects": projects}, ensure_ascii=False)

    try:
        project_dir = _resolve_safe_path(project)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    if not project_dir.is_dir():
        return json.dumps({"error": f"project '{project}' not found"}, ensure_ascii=False)

    files = []
    for f in sorted(project_dir.rglob("*")):
        if f.is_file() and not f.name.startswith("."):
            rel = f.relative_to(project_dir)
            files.append({
                "filename": str(rel),
                "size_bytes": f.stat().st_size,
            })

    return json.dumps({"project": project, "files": files}, ensure_ascii=False)


list_code = Capability(
    name="list_code",
    description=(
        "List projects or files in the custom_code/ directory. "
        "Without 'project': returns all project folder names. "
        "With 'project': returns all files in that project folder with their sizes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project folder name (optional — omit to list all projects)",
            },
        },
        "required": [],
    },
    handler=_handle_list_code,
)


# ---------------------------------------------------------------------------
# read_code
# ---------------------------------------------------------------------------

def _handle_read_code(args: dict) -> str:
    project = args.get("project", "").strip()
    filename = args.get("filename", "").strip()

    if not project:
        return json.dumps({"error": "parameter 'project' is required"}, ensure_ascii=False)
    if not filename:
        return json.dumps({"error": "parameter 'filename' is required"}, ensure_ascii=False)

    try:
        target = _resolve_safe_path(project, filename)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    if not target.is_file():
        return json.dumps({"error": f"file not found: {project}/{filename}"}, ensure_ascii=False)

    size = target.stat().st_size
    if size > _MAX_READ_BYTES:
        return json.dumps({
            "error": f"file too large ({size:,} bytes, limit {_MAX_READ_BYTES:,})",
        }, ensure_ascii=False)

    try:
        content = target.read_text(encoding="utf-8")
        return json.dumps({
            "project": project,
            "filename": filename,
            "content": content,
            "size_bytes": size,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


read_code = Capability(
    name="read_code",
    description=(
        "Read a file from custom_code/<project>/<filename>. "
        "Returns the file content. Use this to review or debug previously written code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "project": {
                "type": "string",
                "description": "Project folder name",
            },
            "filename": {
                "type": "string",
                "description": "File name within the project folder",
            },
        },
        "required": ["project", "filename"],
    },
    handler=_handle_read_code,
)
