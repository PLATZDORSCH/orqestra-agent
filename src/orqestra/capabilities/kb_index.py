"""Knowledge base — indexing, schema, bootstrap."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter

log = logging.getLogger(__name__)

_WIKI_DIRS = [
    "raw/articles", "raw/pdfs", "raw/notes", "raw/docs",
    "wiki/ergebnisse", "wiki/recherche", "wiki/wissen", "wiki/akteure",
]

_SCAFFOLD_FILES: dict[str, tuple[dict, str]] = {
    "wiki/index.md": (
        {"title": "Wiki-Index", "category": "meta", "tags": ["index", "overview"]},
        "# Wiki-Index\n\nAutomatisch gepflegte Übersicht (Statistiken, Kategorien, Verweise).\n",
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


class KnowledgeBaseIndexMixin:
    """FTS bootstrap, schema, incremental index."""

    _DB_FILENAME = ".fts_index.db"

    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        # Set on main knowledge base only: registry snapshot for index (departments).
        self.department_links: list[dict[str, Any]] | None = None
        self._bootstrap()
        self._lock = threading.RLock()
        db_path = self.base / self._DB_FILENAME
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._create_schema()
        self._dedupe_fts()
        self._incremental_reindex()

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
        with self._lock:
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

    def _dedupe_fts(self) -> None:
        """Remove duplicate rows in the FTS5 docs table (FTS5 has no UNIQUE constraint)."""
        with self._lock:
            rows = self._db.execute("SELECT path FROM docs ORDER BY rowid").fetchall()
            seen: set[str] = set()
            for i, (path,) in enumerate(rows):
                if path in seen:
                    pass
                seen.add(path)
            # Simpler: delete all docs and keep only the one with the highest rowid per path
            self._db.executescript("""
                CREATE TEMP TABLE IF NOT EXISTS _keep AS
                    SELECT MAX(rowid) AS rid FROM docs GROUP BY path;
                DELETE FROM docs WHERE rowid NOT IN (SELECT rid FROM _keep);
                DROP TABLE IF EXISTS _keep;
            """)
            self._db.commit()

    def _incremental_reindex(self) -> None:
        """Only (re)index files that are new or modified since last index."""
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS file_mtime ("
                "  path TEXT PRIMARY KEY, mtime REAL"
                ")"
            )

            known: dict[str, float] = {}
            for row in self._db.execute("SELECT path, mtime FROM file_mtime"):
                known[row[0]] = row[1]

            disk_files: dict[str, Path] = {}
            for md in self.base.rglob("*.md"):
                rel = str(md.relative_to(self.base))
                disk_files[rel] = md

            # Remove deleted files
            deleted = set(known) - set(disk_files)
            for rel in deleted:
                self._db.execute("DELETE FROM docs WHERE path=?", (rel,))
                self._db.execute("DELETE FROM meta WHERE path=?", (rel,))
                self._db.execute("DELETE FROM links WHERE source=?", (rel,))
                self._db.execute("DELETE FROM file_mtime WHERE path=?", (rel,))

            # Index new or modified files
            updated = 0
            for rel, md in disk_files.items():
                mtime = md.stat().st_mtime
                if rel in known and known[rel] == mtime:
                    continue
                self._index_one_unlocked(md)
                self._db.execute(
                    "INSERT OR REPLACE INTO file_mtime(path, mtime) VALUES (?,?)",
                    (rel, mtime),
                )
                updated += 1

            self._db.commit()
            total = len(disk_files)
            if deleted or updated:
                log.info(
                    "Knowledge base indexed: %d total, %d updated, %d deleted",
                    total, updated, len(deleted),
                )
            else:
                log.info("Knowledge base: %d documents (all up to date)", total)

    def _index_one_unlocked(self, path: Path) -> None:
        """Update FTS index for one file; caller must hold ``self._lock``."""
        try:
            doc = frontmatter.load(str(path))
        except Exception:
            log.warning("Could not parse %s — skipped", path)
            return
        rel = str(path.relative_to(self.base))
        m = doc.metadata
        tags = " ".join(m.get("tags", []))

        self._db.execute("DELETE FROM docs WHERE path=?", (rel,))
        self._db.execute(
            "INSERT INTO docs(path, title, category, tags, body) VALUES (?,?,?,?,?)",
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

    def _index_one(self, path: Path) -> None:
        with self._lock:
            self._index_one_unlocked(path)
