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

After following a skill and producing the deliverable, the agent must save
the outcome to the wiki via `kb_write` (see system prompt).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from orqestra.core.capabilities import Capability

from orqestra.core.localization import normalize_language, pick_localized_markdown

log = logging.getLogger(__name__)

_skills_dir: Path | None = None
# Orchestrator skill_read: language from engine config (de → prefer *.de.md)
_skill_read_language: str | None = None


def set_skill_read_language(language: str | None) -> None:
    """Called from bootstrap with engine language so skill_read picks localized files."""
    global _skill_read_language
    _skill_read_language = language


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

    # Prefer wiki-lint.de.md when language is de (canonical path is wiki-lint.md)
    if path.suffix == ".md" and not path.name.endswith(".de.md"):
        path = pick_localized_markdown(path, _skill_read_language)

    try:
        skill = _load_skill(path)
        de = normalize_language(_skill_read_language) == "de"
        skill["_wiki_persistence"] = (
            "Pflicht: Nach Ausführung dieses Skills das Endergebnis mit kb_write im Wiki speichern "
            "(z. B. wiki/ergebnisse/... oder wiki/wissen/...), nicht nur in der Chat-Antwort."
            if de
            else "Required: After executing this skill, save the final result with kb_write in the wiki "
            "(e.g. wiki/ergebnisse/... or wiki/wissen/...), not only in the chat reply."
        )
        return json.dumps(skill, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": f"Failed to read skill: {exc}"}, ensure_ascii=False)


def _handle_create(args: dict) -> str:
    skills_dir = _get_dir()
    filename = args["filename"]
    if not filename.endswith(".md"):
        filename += ".md"

    if ".." in filename or filename.startswith("/"):
        return json.dumps(
            {"error": f"Invalid filename (no path traversal allowed): {filename}"},
            ensure_ascii=False,
        )

    path = skills_dir / filename
    if not path.resolve().is_relative_to(skills_dir):
        return json.dumps(
            {"error": f"Path escapes skills directory: {filename}"},
            ensure_ascii=False,
        )

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

    if ".." in filename or filename.startswith("/"):
        return json.dumps(
            {"error": f"Invalid filename (no path traversal allowed): {filename}"},
            ensure_ascii=False,
        )

    path = skills_dir / filename
    if not path.resolve().is_relative_to(skills_dir):
        return json.dumps(
            {"error": f"Path escapes skills directory: {filename}"},
            ensure_ascii=False,
        )

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
        "Use this before executing a procedure to follow the documented steps. "
        "After finishing the procedure, you MUST save the deliverable to the wiki with kb_write "
        "(see response field _wiki_persistence). "
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
        "Create a new skill in the **orchestrator's** root skills/ directory. "
        "ONLY for cross-department or orchestrator-level playbooks (e.g. wiki management, "
        "stakeholder mapping, proposal generation). "
        "Department-specific skills (SEO, marketing, finance, strategy, operations) belong "
        "in the department's own skills/ folder — delegate skill creation to the department instead. "
        "Include: when to use it, prerequisites, detailed steps, expected outputs, and common pitfalls.\n\n"
        "⚠️ CRITICAL: A skill is a REUSABLE PROCEDURE (recipe/playbook), NOT content or deliverables! "
        "The RESULT of executing a skill (e.g. a social-media post, a report, an analysis) is NOT a new skill — "
        "it is a wiki page (use kb_write). Only create a skill if it teaches a genuinely NEW, repeatable method "
        "that does not already exist. Ask yourself: 'Does this describe HOW to do something, or is it WHAT was produced?' "
        "If it's the latter, write it to the wiki instead."
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
        "Update an existing skill in the **orchestrator's** root skills/ directory. "
        "Add edge cases discovered during use, refine steps, fix mistakes, or add better examples. "
        "Version is bumped automatically. "
        "Do NOT update department-specific skills here — delegate that to the department."
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


# ======================================================================
# Factory — create capabilities bound to a specific skills directory
# ======================================================================

def _load_skill_from(skills_dir: Path, path: Path) -> dict:
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


def get_skills_summary_from(skills_dir: Path) -> list[dict[str, Any]]:
    """Return skill summaries for a given directory (used by departments)."""
    results = []
    if not skills_dir.is_dir():
        return results
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


def create_skill_capabilities(
    skills_dir: Path,
    *,
    global_skills_dir: Path | None = None,
    language: str | None = None,
) -> list[Capability]:
    """Return a fresh set of skill_* capabilities bound to *skills_dir*.

    If *global_skills_dir* is given, its skills are also listed/readable
    (read-only — create/update still target the department dir).
    """
    skills_dir = Path(skills_dir).resolve()
    skills_dir.mkdir(parents=True, exist_ok=True)

    _all_dirs: list[Path] = [skills_dir]
    if global_skills_dir and global_skills_dir.resolve() != skills_dir:
        gsd = Path(global_skills_dir).resolve()
        if gsd.is_dir():
            _all_dirs.append(gsd)

    def _match(skill: dict, query: str) -> bool:
        q = query.lower()
        return (
            q in skill["title"].lower()
            or q in skill["description"].lower()
            or any(q in t.lower() for t in skill["tags"])
        )

    def handle_list(args: dict) -> str:
        query = args.get("query", "").strip()
        results = []
        seen_names: set[str] = set()
        for sd in _all_dirs:
            for md in sorted(sd.rglob("*.md")):
                if md.stem in seen_names:
                    continue
                try:
                    skill = _load_skill_from(sd, md)
                except Exception:
                    continue
                if query and not _match(skill, query):
                    continue
                seen_names.add(md.stem)
                results.append({
                    "filename": skill["filename"],
                    "title": skill["title"],
                    "description": skill["description"],
                    "tags": skill["tags"],
                    "version": skill["version"],
                })
        return json.dumps(results, ensure_ascii=False)

    def handle_read(args: dict) -> str:
        filename = args["filename"]
        if not filename.endswith(".md"):
            filename += ".md"
        path: Path | None = None
        for sd in _all_dirs:
            candidate = sd / filename
            if candidate.is_file():
                path = candidate
                break
            for sub in sd.rglob("*.md"):
                if sub.name == filename:
                    path = sub
                    break
            if path:
                break
        if not path or not path.is_file():
            return json.dumps({"error": f"Skill not found: {filename}"}, ensure_ascii=False)
        try:
            base = skills_dir
            for sd in _all_dirs:
                if path.is_relative_to(sd):
                    base = sd
                    break
            if path.suffix == ".md" and not path.name.endswith(".de.md"):
                path = pick_localized_markdown(path, language)
            skill = _load_skill_from(base, path)
            de = normalize_language(language) == "de"
            skill["_wiki_persistence"] = (
                "Pflicht: Nach Ausführung dieses Skills die Ergebnisse mit kb_write im Wiki speichern. "
                "Verteile auf die richtigen Ordner: wiki/akteure/ für Firmen/Personen, "
                "wiki/recherche/ für Quellen und Recherche-Notizen, wiki/wissen/ für dauerhaftes "
                "Fachwissen (Themen, Trends, Markt, Regulierung), wiki/ergebnisse/ für fertige "
                "Deliverables und Analysen. "
                "Lese vorher den Skill 'wiki-ingest' für die genaue Ordner-Zuordnung."
                if de
                else "Required: After executing this skill, save results with kb_write in the wiki. "
                "Use the right folders: wiki/akteure/ for companies/people, wiki/recherche/ for sources, "
                "wiki/wissen/ for durable knowledge, wiki/ergebnisse/ for deliverables. "
                "Read the 'wiki-ingest' skill for folder rules."
            )
            return json.dumps(skill, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Failed to read skill: {exc}"}, ensure_ascii=False)

    def handle_create(args: dict) -> str:
        filename = args["filename"]
        if not filename.endswith(".md"):
            filename += ".md"
        if ".." in filename or filename.startswith("/"):
            return json.dumps({"error": f"Invalid filename (no path traversal): {filename}"}, ensure_ascii=False)
        path = skills_dir / filename
        if not path.resolve().is_relative_to(skills_dir):
            return json.dumps({"error": f"Path escapes skills directory: {filename}"}, ensure_ascii=False)
        if path.exists():
            return json.dumps({"error": f"Skill already exists: {filename}. Use skill_update."}, ensure_ascii=False)
        metadata = args.get("metadata", {})
        if "version" not in metadata:
            metadata["version"] = 1
        if "created" not in metadata:
            metadata["created"] = str(date.today())
        post = frontmatter.Post(args["content"], **metadata)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return json.dumps({"success": True, "filename": filename}, ensure_ascii=False)

    def handle_update(args: dict) -> str:
        filename = args["filename"]
        if not filename.endswith(".md"):
            filename += ".md"
        if ".." in filename or filename.startswith("/"):
            return json.dumps({"error": f"Invalid filename (no path traversal): {filename}"}, ensure_ascii=False)
        path = skills_dir / filename
        if not path.resolve().is_relative_to(skills_dir):
            return json.dumps({"error": f"Path escapes skills directory: {filename}"}, ensure_ascii=False)
        if not path.is_file():
            return json.dumps({"error": f"Skill not found: {filename}"}, ensure_ascii=False)
        try:
            existing = frontmatter.load(str(path))
        except Exception as exc:
            return json.dumps({"error": f"Failed to load skill: {exc}"}, ensure_ascii=False)
        new_metadata = args.get("metadata")
        if new_metadata:
            existing.metadata.update(new_metadata)
        existing.metadata["version"] = existing.metadata.get("version", 1) + 1
        existing.metadata["updated"] = str(date.today())
        if args.get("content") is not None:
            existing.content = args["content"]
        path.write_text(frontmatter.dumps(existing), encoding="utf-8")
        return json.dumps({"success": True, "filename": filename, "version": existing.metadata["version"]}, ensure_ascii=False)

    dept_create_desc = (
        "Create a new skill in YOUR department's skills/ directory. "
        "ONLY for skills specific to your area of expertise. "
        "Do NOT create orchestrator-level or cross-department skills — those belong in the root. "
        "Include: when to use it, prerequisites, detailed steps, expected outputs, and common pitfalls.\n\n"
        "⚠️ CRITICAL: A skill is a REUSABLE PROCEDURE (recipe/playbook), NOT content or deliverables! "
        "The RESULT of running a skill (e.g. a written post, a report, an analysis, a strategy document) "
        "is NOT a new skill — save results to the wiki with kb_write instead. "
        "Only create a skill when it teaches a genuinely NEW, repeatable method that no existing skill covers. "
        "Ask: 'Does this describe HOW to do something, or is it WHAT was produced?' "
        "If it's the latter → kb_write, not skill_create."
    )
    dept_update_desc = (
        "Update an existing skill in YOUR department's skills/ directory. "
        "Add edge cases discovered during use, refine steps, fix mistakes, or add better examples. "
        "Version is bumped automatically. Only update skills that belong to your department."
    )

    return [
        Capability(name="skill_list", description=skill_list.description, parameters=skill_list.parameters, handler=handle_list),
        Capability(name="skill_read", description=skill_read.description, parameters=skill_read.parameters, handler=handle_read),
        Capability(name="skill_create", description=dept_create_desc, parameters=skill_create.parameters, handler=handle_create),
        Capability(name="skill_update", description=dept_update_desc, parameters=skill_update.parameters, handler=handle_update),
    ]
