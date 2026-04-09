"""Skills system — reusable procedural knowledge as Markdown files.

Skills are step-by-step playbooks the agent can consult and follow.
They live in the skills/ directory as .md files with YAML frontmatter.

The agent can:
  - List and search available skills
  - Read a skill to follow its instructions
  - Create new skills after completing a complex task
  - Update existing skills to refine them based on experience

Skill format:

    ---
    title: "SWOT Analysis"
    description: "Conduct a structured SWOT analysis for any company or product."
    tags: [analysis, strategy, frameworks]
    version: 1
    ---

    # SWOT Analysis

    ## When to use
    When the user asks for a strength/weakness assessment ...

    ## Steps
    1. ...
    2. ...

Skills are self-improving: the agent is encouraged to update a skill
after using it, adding edge cases, better prompts, or new steps
discovered during execution.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from core.capabilities import Capability

log = logging.getLogger(__name__)

_skills_dir: Path | None = None


def init_skills(skills_dir: str | Path) -> Path:
    global _skills_dir
    _skills_dir = Path(skills_dir).resolve()
    _skills_dir.mkdir(parents=True, exist_ok=True)
    count = sum(1 for _ in _skills_dir.rglob("*.md"))
    log.info("Skills directory initialized: %d skills", count)
    return _skills_dir


def _get_dir() -> Path:
    if _skills_dir is None:
        raise RuntimeError("Skills not initialized — call init_skills() first")
    return _skills_dir


def get_skills_summary() -> list[dict[str, Any]]:
    """Return a lightweight list of all skills for startup display."""
    skills_dir = _get_dir()
    results = []
    for md in sorted(skills_dir.rglob("*.md")):
        try:
            doc = frontmatter.load(str(md))
            m = doc.metadata
            results.append({
                "name": md.stem,
                "title": m.get("title", md.stem),
                "description": m.get("description", ""),
                "tags": m.get("tags", []),
            })
        except Exception:
            continue
    return results


def _load_skill(path: Path) -> dict:
    """Load a skill file and return structured data."""
    doc = frontmatter.load(str(path))
    return {
        "filename": path.name,
        "title": doc.metadata.get("title", path.stem),
        "description": doc.metadata.get("description", ""),
        "tags": doc.metadata.get("tags", []),
        "version": doc.metadata.get("version", 1),
        "metadata": doc.metadata,
        "content": doc.content,
    }


def _match_query(skill: dict, query: str) -> bool:
    """Check if a skill matches a search query (case-insensitive)."""
    q = query.lower()
    if q in skill["title"].lower():
        return True
    if q in skill["description"].lower():
        return True
    if any(q in tag.lower() for tag in skill["tags"]):
        return True
    return False


# ======================================================================
# Handlers
# ======================================================================

def _handle_list(args: dict) -> str:
    skills_dir = _get_dir()
    query = args.get("query", "").strip()

    results = []
    for md in sorted(skills_dir.rglob("*.md")):
        try:
            skill = _load_skill(md)
        except Exception:
            continue
        if query and not _match_query(skill, query):
            continue
        results.append({
            "filename": skill["filename"],
            "title": skill["title"],
            "description": skill["description"],
            "tags": skill["tags"],
            "version": skill["version"],
        })

    return json.dumps(results, ensure_ascii=False)


def _handle_read(args: dict) -> str:
    skills_dir = _get_dir()
    filename = args["filename"]
    if not filename.endswith(".md"):
        filename += ".md"

    path = skills_dir / filename
    if not path.is_file():
        for candidate in skills_dir.rglob("*.md"):
            if candidate.name == filename:
                path = candidate
                break

    if not path.is_file():
        return json.dumps({"error": f"Skill not found: {filename}"}, ensure_ascii=False)

    try:
        skill = _load_skill(path)
        return json.dumps(skill, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"Failed to read skill: {exc}"}, ensure_ascii=False)


def _handle_create(args: dict) -> str:
    skills_dir = _get_dir()
    filename = args["filename"]
    if not filename.endswith(".md"):
        filename += ".md"

    path = skills_dir / filename
    if path.exists():
        return json.dumps(
            {"error": f"Skill already exists: {filename}. Use skill_update to modify it."},
            ensure_ascii=False,
        )

    metadata = args.get("metadata", {})
    content = args["content"]

    if "version" not in metadata:
        metadata["version"] = 1
    if "created" not in metadata:
        metadata["created"] = str(date.today())

    post = frontmatter.Post(content, **metadata)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")

    log.info("Skill created: %s", filename)
    return json.dumps({"success": True, "filename": filename}, ensure_ascii=False)


def _handle_update(args: dict) -> str:
    skills_dir = _get_dir()
    filename = args["filename"]
    if not filename.endswith(".md"):
        filename += ".md"

    path = skills_dir / filename
    if not path.is_file():
        return json.dumps({"error": f"Skill not found: {filename}"}, ensure_ascii=False)

    try:
        existing = frontmatter.load(str(path))
    except Exception as exc:
        return json.dumps({"error": f"Failed to load skill: {exc}"}, ensure_ascii=False)

    new_metadata = args.get("metadata")
    new_content = args.get("content")

    if new_metadata:
        existing.metadata.update(new_metadata)

    existing.metadata["version"] = existing.metadata.get("version", 1) + 1
    existing.metadata["updated"] = str(date.today())

    if new_content is not None:
        existing.content = new_content

    path.write_text(frontmatter.dumps(existing), encoding="utf-8")

    log.info("Skill updated: %s (v%d)", filename, existing.metadata["version"])
    return json.dumps({
        "success": True,
        "filename": filename,
        "version": existing.metadata["version"],
    }, ensure_ascii=False)


# ======================================================================
# Capability definitions
# ======================================================================

skill_list = Capability(
    name="skill_list",
    description=(
        "List available skills (reusable playbooks and procedures). "
        "Optionally filter by a search query that matches title, description, or tags."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional search query to filter skills"},
        },
    },
    handler=_handle_list,
)

skill_read = Capability(
    name="skill_read",
    description=(
        "Read a skill file to get its full instructions. "
        "Use this before executing a procedure to follow the documented steps."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Filename of the skill (e.g. 'swot-analysis.md')"},
        },
        "required": ["filename"],
    },
    handler=_handle_read,
)

skill_create = Capability(
    name="skill_create",
    description=(
        "Create a new skill after completing a complex task successfully. "
        "Skills are reusable playbooks — step-by-step instructions that can be "
        "followed in future similar tasks. Include: when to use it, prerequisites, "
        "detailed steps, expected outputs, and common pitfalls."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Filename for the skill (e.g. 'competitor-deep-dive.md')"},
            "metadata": {
                "type": "object",
                "description": "YAML header: title, description, tags (array). Version is set automatically.",
            },
            "content": {"type": "string", "description": "Full Markdown content with steps, examples, and notes"},
        },
        "required": ["filename", "content"],
    },
    handler=_handle_create,
)

skill_update = Capability(
    name="skill_update",
    description=(
        "Update an existing skill to improve it — add edge cases discovered during use, "
        "refine steps, fix mistakes, or add better examples. Version is bumped automatically."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Filename of the skill to update"},
            "metadata": {
                "type": "object",
                "description": "Fields to update in the YAML header (merged with existing)",
            },
            "content": {"type": "string", "description": "New full Markdown content (replaces existing)"},
        },
        "required": ["filename"],
    },
    handler=_handle_update,
)
