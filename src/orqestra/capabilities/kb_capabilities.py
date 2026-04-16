"""Capability definitions and factory for the knowledge base."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orqestra.core.capabilities import Capability

from orqestra.capabilities.kb_core import KnowledgeBase

# ======================================================================
# Capability definitions for the agent
# ======================================================================

_kb: KnowledgeBase | None = None
_personal_kb: KnowledgeBase | None = None


def init_knowledge_base(base_dir: str | Path) -> KnowledgeBase:
    global _kb
    _kb = KnowledgeBase(base_dir)
    return _kb


def init_personal_knowledge_base(base_dir: str | Path) -> KnowledgeBase:
    """Second KB for \"Mein Wissen\"; enables merged kb_search / kb_read."""
    global _personal_kb
    _personal_kb = KnowledgeBase(base_dir)
    return _personal_kb


def get_personal_knowledge_base() -> KnowledgeBase | None:
    return _personal_kb


def _get_kb() -> KnowledgeBase:
    if _kb is None:
        raise RuntimeError("KnowledgeBase not initialized — call init_knowledge_base() first")
    return _kb


def _get_personal_or_raise() -> KnowledgeBase:
    if _personal_kb is None:
        raise RuntimeError(
            "Personal knowledge base not initialized — call init_personal_knowledge_base() first"
        )
    return _personal_kb


def _handle_search(args: dict) -> str:
    lim = int(args.get("limit", 10) or 10)
    query = args["query"]
    category = args.get("category")

    results_main, suggestions_main = _get_kb().search(
        query=query,
        category=category,
        limit=lim,
    )
    for r in results_main:
        r["source"] = "main"

    results_pers: list[dict[str, Any]] = []
    suggestions_pers: list[dict] = []
    if _personal_kb is not None:
        results_pers, suggestions_pers = _personal_kb.search(
            query=query,
            category=category,
            limit=lim,
        )
        for r in results_pers:
            r["source"] = "personal"

    all_results: list[dict[str, Any]] = list(results_main) + list(results_pers)
    if len(all_results) > lim:
        all_results = all_results[:lim]

    out: dict[str, Any] = {"results": all_results}
    if not all_results:
        seen: set[tuple[str, str | None]] = set()
        merged_sug: list[dict[str, Any]] = []
        for s in suggestions_main:
            key = (str(s.get("path", "")), s.get("matched_term"))
            if key in seen:
                continue
            seen.add(key)
            s2 = dict(s)
            s2["source"] = "main"
            merged_sug.append(s2)
        for s in suggestions_pers:
            key = (str(s.get("path", "")), s.get("matched_term"))
            if key in seen:
                continue
            seen.add(key)
            s2 = dict(s)
            s2["source"] = "personal"
            merged_sug.append(s2)
        if merged_sug:
            out["suggestions"] = merged_sug
            out["hint"] = (
                "Keine exakten Treffer für die Kombination. "
                "Meintest du vielleicht eine dieser Seiten (siehe suggestions)?"
            )
    return json.dumps(out, ensure_ascii=False)


def _handle_read(args: dict) -> str:
    path = args["path"]
    result = _get_kb().read(path)
    if "error" not in result:
        result["source"] = "main"
        return json.dumps(result, ensure_ascii=False, default=str)
    if _personal_kb is not None:
        result_p = _personal_kb.read(path)
        if "error" not in result_p:
            result_p["source"] = "personal"
            return json.dumps(result_p, ensure_ascii=False, default=str)
    return json.dumps(result, ensure_ascii=False, default=str)


def _handle_write(args: dict) -> str:
    return json.dumps(
        _get_kb().write(args["path"], args.get("metadata", {}), args["content"]),
        ensure_ascii=False,
    )


def _handle_list(args: dict) -> str:
    return json.dumps(
        _get_kb().list_entries(category=args.get("category"), tag=args.get("tag")),
        ensure_ascii=False,
    )


def _handle_delete(args: dict) -> str:
    return json.dumps(_get_kb().delete(args["path"]), ensure_ascii=False)


def _handle_related(args: dict) -> str:
    kb = _get_kb()
    paths = kb.related(args["path"], depth=args.get("depth", 2))
    entries = []
    for p in paths:
        title, cat = kb.doc_title_category(p)
        entries.append({"path": p, "title": title, "category": cat})
    return json.dumps(entries, ensure_ascii=False)


def _handle_my_write(args: dict) -> str:
    return json.dumps(
        _get_personal_or_raise().write(args["path"], args.get("metadata", {}), args["content"]),
        ensure_ascii=False,
    )


def _handle_my_list(args: dict) -> str:
    return json.dumps(
        _get_personal_or_raise().list_entries(category=args.get("category"), tag=args.get("tag")),
        ensure_ascii=False,
    )


def _handle_my_delete(args: dict) -> str:
    return json.dumps(_get_personal_or_raise().delete(args["path"]), ensure_ascii=False)


def _handle_my_related(args: dict) -> str:
    kb = _get_personal_or_raise()
    paths = kb.related(args["path"], depth=args.get("depth", 2))
    entries = []
    for p in paths:
        title, cat = kb.doc_title_category(p)
        entries.append({"path": p, "title": title, "category": cat})
    return json.dumps(entries, ensure_ascii=False)


kb_search = Capability(
    name="kb_search",
    description=(
        "Search the **main company wiki** and **personal wiki (Mein Wissen)** using full-text search "
        "(OR + prefix matching on tokens). Each result includes \"source\": \"main\" or \"personal\". "
        "Returns JSON: {\"results\": [...]}; if nothing matches the combined query but related pages exist per word, "
        "also \"suggestions\" and \"hint\" — offer those pages to the user when relevant. "
        "Covers raw/ and wiki/ in both KBs. Optionally filter by category."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term(s)"},
            "category": {
                "type": "string",
                "description": "Filter by category: ergebnisse, recherche, wissen, akteure",
            },
            "limit": {"type": "integer", "description": "Max number of results (default: 10)"},
        },
        "required": ["query"],
    },
    handler=_handle_search,
)

kb_read = Capability(
    name="kb_read",
    description=(
        "Read a single entry from the knowledge base. Tries the **main wiki** first, then **Mein Wissen** "
        "if the path is not found. Response includes \"source\": \"main\" or \"personal\" on success. "
        "Path is relative to the KB root, e.g. 'wiki/wissen/ai-agents.md', 'wiki/index.md'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to the Markdown document"},
        },
        "required": ["path"],
    },
    handler=_handle_read,
)

kb_write = Capability(
    name="kb_write",
    description=(
        "Create or update a wiki page in the **main (company) knowledge base** — this is the default for saving. "
        "Use **`my_kb_write`** only when the user explicitly asks to store something in **Mein Wissen** (personal wiki). "
        "CRITICAL — use the CORRECT folder for each content type: "
        "• wiki/akteure/name.md — one page PER company, person, or organization; "
        "• wiki/recherche/ — source summaries, ingested sources, research notes (e.g. YYYY-MM-DD-name.md); "
        "• wiki/wissen/ — durable knowledge: topics, trends, market facts, regulations, general reference; "
        "• wiki/ergebnisse/ — finished deliverables, analyses, reports, content briefs, syntheses. "
        "Do NOT dump everything into ergebnisse/ — use akteure/ for entities and wissen/ for reference knowledge. "
        "Every company/competitor analyzed MUST get its own page in wiki/akteure/. "
        "Also valid: 'raw/articles/YYYY-MM-DD-name.md'. "
        "NEVER modify existing files in raw/ — only create new ones there. "
        "If you omit created/updated in metadata, the server sets them automatically. "
        "For **background department jobs**, the server injects metadata.job_id; default job_role is supporting. "
        "Set job_role to **deliverable** on the ONE primary output page (usually under wiki/ergebnisse/); use **supporting** for "
        "akteure/recherche/wissen pages created along the way."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path (e.g. 'wiki/wissen/ai-agents.md', 'wiki/index.md')",
            },
            "metadata": {
                "type": "object",
                "description": (
                    "YAML header fields: title, category (ergebnisse|recherche|wissen|akteure), "
                    "created, updated (ISO date YYYY-MM-DD — if omitted, server sets them to today on save; updates preserve existing created), "
                    "tags (array), sources (array of paths), status (active|draft|stale|archived). "
                    "For akteure: player_type. For recherche: source_type, source_path, ingested. "
                    "For department jobs: job_id (usually auto-set), job_role (deliverable|supporting) — mark exactly one deliverable page."
                ),
            },
            "content": {"type": "string", "description": "Markdown body including a 'Related Pages' section with cross-references"},
        },
        "required": ["path", "content"],
    },
    handler=_handle_write,
)

kb_list = Capability(
    name="kb_list",
    description=(
        "List knowledge base entries, optionally filtered by category or tag. "
        "Categories: ergebnisse, recherche, wissen, akteure."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Filter: ergebnisse, recherche, wissen, akteure",
            },
            "tag": {"type": "string", "description": "Only show entries with this tag"},
        },
    },
    handler=_handle_list,
)

kb_delete = Capability(
    name="kb_delete",
    description=(
        "Delete a wiki page and automatically clean up ALL cross-references in other pages, "
        "the index, and the operations log. "
        "Protected pages (index.md, log.md, memory.md) cannot be deleted. "
        "Returns the list of pages whose references were cleaned."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path to the page to delete (e.g. 'wiki/akteure/acme.md')",
            },
        },
        "required": ["path"],
    },
    handler=_handle_delete,
)

kb_related = Capability(
    name="kb_related",
    description="Find all documents linked to a given entry (via cross-references, up to the specified depth).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path of the starting document"},
            "depth": {"type": "integer", "description": "Traversal depth (default: 2)"},
        },
        "required": ["path"],
    },
    handler=_handle_related,
)

my_kb_write = Capability(
    name="my_kb_write",
    description=(
        "Create or update a page in **Mein Wissen** (your personal knowledge base). "
        "Use **only** when the user explicitly asks to save something personal/private, or to "
        "write into personal wiki. Default for all other saves remains **`kb_write`** (main wiki) or "
        "department tools. Same folder conventions as the main wiki (wiki/wissen/, wiki/akteure/, wiki/recherche/, wiki/ergebnisse/)."
    ),
    parameters=kb_write.parameters,
    handler=_handle_my_write,
)

my_kb_delete = Capability(
    name="my_kb_delete",
    description=(
        "Delete a page from **Mein Wissen** (personal wiki) and clean up cross-references. "
        "Protected pages behave like the main KB."
    ),
    parameters=kb_delete.parameters,
    handler=_handle_my_delete,
)

my_kb_list = Capability(
    name="my_kb_list",
    description="List entries in **Mein Wissen** (personal wiki), optionally filtered by category or tag.",
    parameters=kb_list.parameters,
    handler=_handle_my_list,
)

my_kb_related = Capability(
    name="my_kb_related",
    description=(
        "Find documents linked to an entry in **Mein Wissen** (personal wiki), up to the given depth."
    ),
    parameters=kb_related.parameters,
    handler=_handle_my_related,
)


# ======================================================================
# Factory — create capabilities bound to a specific KnowledgeBase instance
# ======================================================================


def create_kb_capabilities(kb: KnowledgeBase) -> list[Capability]:
    """Return a fresh set of kb_* capabilities bound to *kb*."""

    def _search(args: dict) -> str:
        results, suggestions = kb.search(
            args["query"],
            args.get("category"),
            args.get("limit", 10),
        )
        out: dict[str, Any] = {"results": results}
        if suggestions:
            out["suggestions"] = suggestions
            out["hint"] = (
                "Keine exakten Treffer für die Kombination. "
                "Meintest du vielleicht eine dieser Seiten (siehe suggestions)?"
            )
        return json.dumps(out, ensure_ascii=False)

    def _read(args: dict) -> str:
        return json.dumps(kb.read(args["path"]), ensure_ascii=False, default=str)

    def _write(args: dict) -> str:
        return json.dumps(
            kb.write(args["path"], args.get("metadata", {}), args["content"]),
            ensure_ascii=False,
        )

    def _list(args: dict) -> str:
        return json.dumps(
            kb.list_entries(args.get("category"), args.get("tag")),
            ensure_ascii=False,
        )

    def _delete(args: dict) -> str:
        return json.dumps(kb.delete(args["path"]), ensure_ascii=False)

    def _related(args: dict) -> str:
        paths = kb.related(args["path"], args.get("depth", 2))
        entries = []
        for p in paths:
            title, cat = kb.doc_title_category(p)
            entries.append({"path": p, "title": title, "category": cat})
        return json.dumps(entries, ensure_ascii=False)

    return [
        Capability(name="kb_search", description=kb_search.description, parameters=kb_search.parameters, handler=_search),
        Capability(name="kb_read", description=kb_read.description, parameters=kb_read.parameters, handler=_read),
        Capability(name="kb_write", description=kb_write.description, parameters=kb_write.parameters, handler=_write),
        Capability(name="kb_delete", description=kb_delete.description, parameters=kb_delete.parameters, handler=_delete),
        Capability(name="kb_list", description=kb_list.description, parameters=kb_list.parameters, handler=_list),
        Capability(name="kb_related", description=kb_related.description, parameters=kb_related.parameters, handler=_related),
    ]
