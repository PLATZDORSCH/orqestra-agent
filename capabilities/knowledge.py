"""Knowledge base — Three-layer Markdown wiki with YAML frontmatter and FTS5 search.

Architecture:
    raw/          Immutable source documents (articles, PDFs, notes)
    wiki/         Structured, interlinked wiki pages (topics, trends, players, etc.)
    content/      Publishable content derived from wiki (drafts, templates)

All .md files are indexed recursively. A SQLite FTS5 index provides fast
full-text search. Cross-references are tracked both from YAML `sources` fields
and from inline Markdown links [text](path.md).

Wiki page format:

    ---
    title: "AI Agents in Business"
    category: topics
    created: 2026-04-08
    updated: 2026-04-08
    tags: [ai, automation]
    sources: [source-1.md]
    status: active
    ---

    # AI Agents in Business
    Content ...

    ## Related Pages
    - [Trend: AI Agents](../trends/ai-agents.md)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

from core.capabilities import Capability

log = logging.getLogger(__name__)


_WIKI_DIRS = [
    "raw/articles", "raw/pdfs", "raw/notes",
    "wiki/topics", "wiki/trends", "wiki/regulation",
    "wiki/market", "wiki/players", "wiki/sources", "wiki/synthesis",
    "content/drafts", "content/published", "content/templates",
]

_SCAFFOLD_FILES: dict[str, tuple[dict, str]] = {
    "wiki/index.md": (
        {"title": "Wiki Index", "category": "meta", "tags": ["index"]},
        "# Wiki Index\n\nCatalog of all wiki pages.\n",
    ),
    "wiki/overview.md": (
        {"title": "Industry Overview", "category": "meta", "tags": ["overview"]},
        "# Industry Overview\n\nHigh-level overview — updated as knowledge grows.\n",
    ),
    "wiki/log.md": (
        {"title": "Operations Log", "category": "meta", "tags": ["log"]},
        "# Operations Log\n\nChronological log of wiki operations (append-only).\n",
    ),
    "wiki/memory.md": (
        {"title": "Agent Memory", "category": "meta", "tags": ["memory"]},
        (
            "# Agent Memory\n\n"
            "## User / project context\n\n"
            "_(no entries yet)_\n\n"
            "## Working preferences\n\n"
            "_(no entries yet)_\n\n"
            "## Linked analyses\n\n"
            "_(no entries yet)_\n"
        ),
    ),
}


class KnowledgeBase:
    """In-process Markdown wiki backed by a SQLite FTS5 search index."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        self._bootstrap()
        self._db = sqlite3.connect(":memory:")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._create_schema()
        self._reindex()

    def _bootstrap(self) -> None:
        """Create folder structure and scaffold files on first run."""
        for d in _WIKI_DIRS:
            (self.base / d).mkdir(parents=True, exist_ok=True)

        for rel_path, (meta, body) in _SCAFFOLD_FILES.items():
            full = self.base / rel_path
            if full.exists():
                continue
            meta_copy = {**meta, "created": str(date.today()), "updated": str(date.today())}
            post = frontmatter.Post(body, **meta_copy)
            full.write_text(frontmatter.dumps(post), encoding="utf-8")
            log.info("Scaffold created: %s", rel_path)

    def _create_schema(self) -> None:
        self._db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs
            USING fts5(path, title, category, tags, body, tokenize='unicode61');

            CREATE TABLE IF NOT EXISTS meta (
                path     TEXT PRIMARY KEY,
                raw_yaml TEXT
            );

            CREATE TABLE IF NOT EXISTS links (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                UNIQUE(source, target)
            );
        """)

    def _reindex(self) -> None:
        self._db.execute("DELETE FROM docs")
        self._db.execute("DELETE FROM meta")
        self._db.execute("DELETE FROM links")
        count = 0
        for md in self.base.rglob("*.md"):
            self._index_one(md)
            count += 1
        self._db.commit()
        log.info("Knowledge base indexed: %d documents", count)

    def _index_one(self, path: Path) -> None:
        try:
            doc = frontmatter.load(str(path))
        except Exception:
            log.warning("Could not parse %s — skipped", path)
            return
        rel = str(path.relative_to(self.base))
        m = doc.metadata
        tags = " ".join(m.get("tags", []))

        self._db.execute(
            "INSERT OR REPLACE INTO docs(path, title, category, tags, body) VALUES (?,?,?,?,?)",
            (rel, m.get("title", ""), m.get("category", ""), tags, doc.content),
        )
        self._db.execute(
            "INSERT OR REPLACE INTO meta(path, raw_yaml) VALUES (?,?)",
            (rel, json.dumps(m, ensure_ascii=False, default=str)),
        )
        self._db.execute("DELETE FROM links WHERE source=?", (rel,))
        for ref in m.get("references", []):
            self._db.execute(
                "INSERT OR IGNORE INTO links(source, target) VALUES (?,?)",
                (rel, ref),
            )
        for inline_ref in re.findall(r'\[.*?\]\(([^)]+\.md)\)', doc.content):
            self._db.execute(
                "INSERT OR IGNORE INTO links(source, target) VALUES (?,?)",
                (rel, inline_ref),
            )

    # ------------------------------------------------------------------
    # Public methods (called by capability handlers)
    # ------------------------------------------------------------------

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict]:
        fts_query = query.replace('"', '""')
        sql = (
            "SELECT path, title, category, "
            "snippet(docs, 4, '>>', '<<', '...', 48) AS snippet "
            "FROM docs WHERE docs MATCH ?"
        )
        params: list[Any] = [f'"{fts_query}"']

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = self._db.execute(sql, params).fetchall()
        return [
            {"path": r[0], "title": r[1], "category": r[2], "snippet": r[3]}
            for r in rows
        ]

    def read(self, path: str) -> dict:
        full = self.base / path
        if not full.is_file():
            return {"error": f"Not found: {path}"}
        doc = frontmatter.load(str(full))
        return {"path": path, "metadata": doc.metadata, "content": doc.content}

    def write(self, path: str, metadata: dict, content: str) -> dict:
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)

        if "updated" not in metadata:
            metadata["updated"] = str(date.today())

        post = frontmatter.Post(content, **metadata)
        full.write_text(frontmatter.dumps(post), encoding="utf-8")
        self._index_one(full)
        self._db.commit()
        return {"success": True, "path": path}

    def list_entries(self, category: str | None = None, tag: str | None = None) -> list[dict]:
        sql = "SELECT path, title, category, tags FROM docs WHERE 1=1"
        params: list[Any] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if tag:
            sql += " AND tags MATCH ?"
            params.append(tag)
        sql += " ORDER BY title"

        rows = self._db.execute(sql, params).fetchall()
        return [
            {"path": r[0], "title": r[1], "category": r[2], "tags": r[3]}
            for r in rows
        ]

    def related(self, path: str, depth: int = 2) -> list[str]:
        """Traverse reference chains up to the given depth."""
        visited: set[str] = set()
        frontier = {path}
        for _ in range(depth):
            next_level: set[str] = set()
            for p in frontier:
                if p in visited:
                    continue
                visited.add(p)
                rows = self._db.execute(
                    "SELECT target FROM links WHERE source=? "
                    "UNION SELECT source FROM links WHERE target=?",
                    (p, p),
                ).fetchall()
                next_level.update(r[0] for r in rows)
            frontier = next_level - visited
        visited.discard(path)
        return sorted(visited)


# ======================================================================
# Capability definitions for the agent
# ======================================================================

_kb: KnowledgeBase | None = None


def init_knowledge_base(base_dir: str | Path) -> KnowledgeBase:
    global _kb
    _kb = KnowledgeBase(base_dir)
    return _kb


def _get_kb() -> KnowledgeBase:
    if _kb is None:
        raise RuntimeError("KnowledgeBase not initialized — call init_knowledge_base() first")
    return _kb


def _handle_search(args: dict) -> str:
    results = _get_kb().search(
        query=args["query"],
        category=args.get("category"),
        limit=args.get("limit", 10),
    )
    return json.dumps(results, ensure_ascii=False)


def _handle_read(args: dict) -> str:
    return json.dumps(_get_kb().read(args["path"]), ensure_ascii=False, default=str)


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


def _handle_related(args: dict) -> str:
    paths = _get_kb().related(args["path"], depth=args.get("depth", 2))
    entries = []
    for p in paths:
        row = _get_kb()._db.execute(
            "SELECT title, category FROM docs WHERE path=?", (p,)
        ).fetchone()
        entries.append({"path": p, "title": row[0] if row else "", "category": row[1] if row else ""})
    return json.dumps(entries, ensure_ascii=False)


kb_search = Capability(
    name="kb_search",
    description=(
        "Search the knowledge base using full-text search. "
        "Covers all three layers: raw/ (sources), wiki/ (topics, trends, regulation, market, players, sources, synthesis), "
        "and content/ (drafts, templates). Optionally filter by category."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term(s)"},
            "category": {
                "type": "string",
                "description": "Filter by category: topics, trends, regulation, market, players, sources, synthesis",
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
        "Read a single entry from the knowledge base. Path is relative to knowledge_base/, "
        "e.g. 'wiki/topics/ai-agents.md', 'wiki/index.md', 'raw/articles/2026-04-08-report.md', "
        "'content/templates/blog.md'."
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
        "Create or update a wiki page or save a raw source. "
        "Paths: 'wiki/topics/name.md', 'wiki/trends/name.md', 'wiki/players/name.md', "
        "'wiki/sources/YYYY-MM-DD-name.md', 'wiki/synthesis/name.md', 'wiki/index.md', "
        "'raw/articles/YYYY-MM-DD-name.md', 'content/drafts/YYYY-MM-DD-name.md'. "
        "NEVER modify existing files in raw/ — only create new ones there."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path (e.g. 'wiki/topics/ai-agents.md', 'wiki/index.md')",
            },
            "metadata": {
                "type": "object",
                "description": (
                    "YAML header fields: title, category (topics|trends|regulation|market|players|sources|synthesis), "
                    "created, updated, tags (array), sources (array of paths), status (active|draft|stale|archived). "
                    "For trends: first_seen, momentum, relevance. For players: player_type. "
                    "For sources: source_type, source_path, ingested."
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
        "Categories: topics, trends, regulation, market, players, sources, synthesis."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Filter: topics, trends, regulation, market, players, sources, synthesis",
            },
            "tag": {"type": "string", "description": "Only show entries with this tag"},
        },
    },
    handler=_handle_list,
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
