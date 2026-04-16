"""Knowledge base — CRUD, search, navigation rebuild."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import frontmatter

from orqestra.capabilities.kb_fts import (
    _build_fts_or_query,
    _fts5_prefix_term,
    _normalize_metadata,
    _tokenize_search_query,
)

log = logging.getLogger(__name__)


class KnowledgeBaseCrudMixin:
    """Search, read/write, delete, related — uses index methods from KnowledgeBaseIndexMixin."""

    def search(self, query: str, category: str | None = None, limit: int = 10) -> tuple[list[dict], list[dict]]:
        """Full-text search with OR + prefix matching. Returns (results, suggestions).

        When the combined query yields no rows but multiple tokens were used,
        suggestions lists top hits per token (deduplicated) so the agent can
        offer related pages (e.g. \"KI für Autowerkstätten\" when searching for
        \"Digitalisierung in Autowerkstätten\").
        """
        if not (query or "").strip():
            return [], []

        words = _tokenize_search_query(query)
        fts_query = _build_fts_or_query(words)
        if not fts_query:
            fts_query = _fts5_prefix_term(query.strip()) or query.replace('"', '""')

        sql = (
            "SELECT path, title, category, "
            "snippet(docs, 4, '>>', '<<', '...', 48) AS snippet "
            "FROM docs WHERE docs MATCH ?"
        )
        params: list[Any] = [fts_query]

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
        results = [
            {"path": r[0], "title": r[1], "category": r[2], "snippet": r[3]}
            for r in rows
        ]

        suggestions: list[dict] = []
        if not results and len(words) > 1:
            seen: set[str] = set()
            sub_sql_base = (
                "SELECT path, title, category, "
                "snippet(docs, 4, '>>', '<<', '...', 48) AS snippet "
                "FROM docs WHERE docs MATCH ?"
            )
            for w in words:
                sub_q = _fts5_prefix_term(w)
                if not sub_q:
                    continue
                sub_sql = sub_sql_base
                sub_params: list[Any] = [sub_q]
                if category:
                    sub_sql += " AND category = ?"
                    sub_params.append(category)
                sub_sql += " ORDER BY rank LIMIT 3"
                sub_rows = self._db.execute(sub_sql, sub_params).fetchall()
                for r in sub_rows:
                    if r[0] not in seen:
                        seen.add(r[0])
                        suggestions.append({
                            "path": r[0],
                            "title": r[1],
                            "category": r[2],
                            "snippet": r[3],
                            "matched_term": w,
                        })

        return results, suggestions

    def read(self, path: str) -> dict:
        full = self.base / path
        if not full.is_file():
            return {"error": f"Not found: {path}"}
        doc = frontmatter.load(str(full))
        return {"path": path, "metadata": doc.metadata, "content": doc.content}

    _META_PATHS = {"wiki/index.md", "wiki/log.md", "wiki/memory.md"}

    def write(self, path: str, metadata: Any, content: str) -> dict:
        metadata = _normalize_metadata(metadata)
        full = self.base / path
        full.parent.mkdir(parents=True, exist_ok=True)
        today = str(date.today())
        is_update = full.is_file()

        if is_update:
            try:
                existing = frontmatter.load(str(full))
                if "created" not in metadata and existing.metadata.get("created"):
                    metadata["created"] = existing.metadata["created"]
            except Exception:
                pass
        elif "created" not in metadata:
            metadata["created"] = today

        if "updated" not in metadata:
            metadata["updated"] = today

        post = frontmatter.Post(content, **metadata)
        full.write_text(frontmatter.dumps(post), encoding="utf-8")
        with self._lock:
            self._index_one_unlocked(full)
            mtime = full.stat().st_mtime
            self._db.execute(
                "INSERT OR REPLACE INTO file_mtime(path, mtime) VALUES (?,?)",
                (path, mtime),
            )
            self._db.commit()

        if path not in self._META_PATHS:
            title = metadata.get("title", Path(path).stem)
            self._auto_append_log(path, title, is_update=is_update)
            self._auto_rebuild_index()

        return {"success": True, "path": path}

    # ------------------------------------------------------------------
    # Automatic wiki/index.md and wiki/log.md maintenance
    # ------------------------------------------------------------------

    def _auto_append_log(
        self, path: str, title: str, *, is_update: bool = False, action_verb: str | None = None,
    ) -> None:
        """Append a timestamped entry to wiki/log.md."""
        log_path = self.base / "wiki" / "log.md"
        if not log_path.exists():
            return
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            action = action_verb or ("updated" if is_update else "created")
            entry = f"- **{ts}** — {action} `{path}` ({title})\n"
            doc = frontmatter.load(str(log_path))
            doc.content = doc.content.rstrip() + "\n" + entry
            doc.metadata["updated"] = str(date.today())
            log_path.write_text(frontmatter.dumps(doc), encoding="utf-8")
            with self._lock:
                self._index_one_unlocked(log_path)
                self._db.execute(
                    "INSERT OR REPLACE INTO file_mtime(path, mtime) VALUES (?,?)",
                    ("wiki/log.md", log_path.stat().st_mtime),
                )
                self._db.commit()
        except Exception:
            log.debug("Auto-log append failed", exc_info=True)

    def _wiki_stats_excluding_meta(self) -> tuple[int, dict[str, int], tuple[str, str] | None]:
        """Count wiki pages (non-meta), category histogram, and most recently updated page."""
        entries = self.list_entries()
        wiki_entries = [
            e for e in entries
            if e["path"].startswith("wiki/") and e["path"] not in self._META_PATHS
        ]
        categories: dict[str, int] = {}
        for e in wiki_entries:
            c = e.get("category") or "uncategorized"
            categories[c] = categories.get(c, 0) + 1
        latest: tuple[str, str, str] | None = None
        for e in wiki_entries:
            doc = self.read(e["path"])
            meta = doc.get("metadata") or {}
            u = str(meta.get("updated", "") or meta.get("created", ""))
            title = str(meta.get("title") or e.get("title") or Path(e["path"]).stem)
            if latest is None or u > latest[0]:
                latest = (u, e["path"], title)
        latest_pt: tuple[str, str] | None = None
        if latest:
            latest_pt = (latest[1], latest[2])
        return len(wiki_entries), categories, latest_pt

    def refresh_navigation_pages(self) -> None:
        """Regenerate wiki/index.md (e.g. after department registry changes)."""
        self._auto_rebuild_index()

    def _auto_rebuild_index(self) -> None:
        """Rebuild wiki/index.md: statistics, department info, and catalog from FTS."""
        index_path = self.base / "wiki" / "index.md"
        if not index_path.exists():
            return
        try:
            page_count, categories, latest = self._wiki_stats_excluding_meta()
            today = str(date.today())
            with self._lock:
                rows = self._db.execute(
                    "SELECT path, title, category FROM docs "
                    "WHERE path LIKE 'wiki/%' "
                    "ORDER BY category, title"
                ).fetchall()

            by_category: dict[str, list[tuple[str, str]]] = {}
            for r_path, r_title, r_cat in rows:
                if r_path in self._META_PATHS:
                    continue
                cat = r_cat or "uncategorized"
                by_category.setdefault(cat, []).append((r_path, r_title or r_path))

            lines = ["# Wiki-Index", "", f"Stand: **{today}**", ""]

            if self.department_links is None:
                lines.append("## Dieses Wiki")
                lines.append("")
                lines.append(f"- **{page_count}** Seiten in **{len(categories)}** Kategorien")
                if categories:
                    top = sorted(categories.items(), key=lambda x: (-x[1], x[0]))[:5]
                    cat_str = ", ".join(f"{k} ({v})" for k, v in top)
                    lines.append(f"- Schwerpunkte: {cat_str}")
                if latest:
                    lp, lt = latest
                    lines.append(f"- Zuletzt bearbeitet: [{lt}]({lp})")
                lines.append("")
            else:
                lines.append("## Hauptwiki")
                lines.append("")
                lines.append(f"- **{page_count}** Seiten in **{len(categories)}** Kategorien")
                if latest:
                    lp, lt = latest
                    lines.append(f"- Zuletzt bearbeitet: [{lt}]({lp})")
                lines.append("")
                if self.department_links:
                    lines.append("## Department-Wikis")
                    lines.append("")
                    for d in self.department_links:
                        name = d.get("name", "")
                        label = d.get("label", name)
                        idx = d.get("index_path") or "wiki/index.md"
                        n_pages = int(d.get("page_count", 0))
                        url = f"/wiki?dept={quote(name)}&path={quote(idx)}"
                        lines.append(f"### {label}")
                        lines.append("")
                        lines.append(f"- **[Wiki öffnen]({url})** — {n_pages} Seiten")
                        tc = d.get("top_categories")
                        if tc:
                            lines.append(f"- Kategorien: {tc}")
                        rp = d.get("recent_path")
                        rt = d.get("recent_title")
                        if rp and rt:
                            rurl = f"/wiki?dept={quote(name)}&path={quote(rp)}"
                            lines.append(f"- Zuletzt bearbeitet: [{rt}]({rurl})")
                        lines.append("")

            if not by_category:
                lines.append("_(noch keine Einträge)_")
                lines.append("")
            else:
                for cat in sorted(by_category):
                    lines.append(f"## {cat.title()}")
                    lines.append("")
                    for entry_path, entry_title in sorted(by_category[cat], key=lambda x: x[1]):
                        lines.append(f"- [{entry_title}]({entry_path}) — `{entry_path}`")
                    lines.append("")

            body = "\n".join(lines)
            meta = {
                "title": "Wiki-Index",
                "category": "meta",
                "tags": ["index", "overview"],
                "updated": today,
            }
            existing_doc = frontmatter.load(str(index_path))
            if existing_doc.metadata.get("created"):
                meta["created"] = existing_doc.metadata["created"]
            else:
                meta["created"] = str(date.today())

            post = frontmatter.Post(body, **meta)
            index_path.write_text(frontmatter.dumps(post), encoding="utf-8")
            with self._lock:
                self._index_one_unlocked(index_path)
                self._db.execute(
                    "INSERT OR REPLACE INTO file_mtime(path, mtime) VALUES (?,?)",
                    ("wiki/index.md", index_path.stat().st_mtime),
                )
                self._db.commit()
        except Exception:
            log.debug("Auto-index rebuild failed", exc_info=True)

    _PROTECTED_PATHS = {"wiki/index.md", "wiki/log.md", "wiki/memory.md"}

    def delete(self, path: str) -> dict:
        """Delete a wiki page and clean up all cross-references in other pages."""
        if path in self._PROTECTED_PATHS:
            return {"error": f"Cannot delete protected page: {path}"}

        full = self.base / path
        if not full.is_file():
            return {"error": f"Not found: {path}"}

        # 1. Collect title before deletion (for log)
        try:
            doc = frontmatter.load(str(full))
            title = doc.metadata.get("title", Path(path).stem)
        except Exception:
            title = Path(path).stem

        # 2. Find all pages that reference the deleted path
        with self._lock:
            referencing_rows = self._db.execute(
                "SELECT DISTINCT source FROM links WHERE target=?", (path,)
            ).fetchall()
        referencing_paths = [r[0] for r in referencing_rows]

        # 3. Clean cross-references in each referencing page
        for ref_path in referencing_paths:
            ref_full = self.base / ref_path
            if not ref_full.is_file() or ref_path == path:
                continue
            self._remove_references_to(ref_full, ref_path, path)

        # 4. Delete the file from disk
        full.unlink()

        # 5. Remove from all DB tables
        with self._lock:
            self._db.execute("DELETE FROM docs WHERE path=?", (path,))
            self._db.execute("DELETE FROM meta WHERE path=?", (path,))
            self._db.execute("DELETE FROM links WHERE source=? OR target=?", (path, path))
            self._db.execute("DELETE FROM file_mtime WHERE path=?", (path,))
            self._db.commit()

        # 6. Rebuild index.md and log the deletion
        self._auto_append_log(path, title, is_update=False, action_verb="deleted")
        self._auto_rebuild_index()

        cleaned = [p for p in referencing_paths if (self.base / p).is_file()]
        return {
            "success": True,
            "deleted": path,
            "cleaned_references_in": cleaned,
        }

    def _remove_references_to(self, ref_full: Path, ref_path: str, deleted_path: str) -> None:
        """Remove all markdown links and frontmatter references to *deleted_path* from a page."""
        try:
            doc = frontmatter.load(str(ref_full))
        except Exception:
            return

        content: str = doc.content
        changed = False

        # Remove inline markdown links: [text](deleted_path) → text
        # Handle both exact path and relative variants
        deleted_variants = self._link_variants(ref_path, deleted_path)
        for variant in deleted_variants:
            escaped = re.escape(variant)
            pattern = rf'\[([^\]]*)\]\({escaped}\)'
            if re.search(pattern, content):
                content = re.sub(pattern, r'\1', content)
                changed = True

        # Remove bullet lines that are now empty or only contain the former link text
        # e.g. "- [Title](deleted.md)" becomes "- Title" — remove the whole line if it's just that
        lines = content.split('\n')
        cleaned_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Remove lines that were pure link references to the deleted page
            if stripped.startswith('- ') and not any(c in stripped for c in ['](', '**', '|']):
                # After link removal this might just be "- SomeTitle" — keep it
                cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)

        # Remove bullet lines that still contain a raw reference to the deleted path
        lines = content.split('\n')
        cleaned_lines = []
        for line in lines:
            if any(variant in line for variant in deleted_variants):
                stripped = line.strip()
                if stripped.startswith('- ') or stripped.startswith('* '):
                    changed = True
                    continue
            cleaned_lines.append(line)
        content = '\n'.join(cleaned_lines)

        # Clean empty "Related Pages" sections
        content = re.sub(
            r'(## Related Pages\s*\n)(\s*\n)+(?=\n|$|## )',
            '',
            content,
        )

        # Clean frontmatter sources array
        sources = doc.metadata.get("sources", [])
        if isinstance(sources, list) and deleted_path in sources:
            doc.metadata["sources"] = [s for s in sources if s != deleted_path]
            changed = True

        references = doc.metadata.get("references", [])
        if isinstance(references, list) and deleted_path in references:
            doc.metadata["references"] = [r for r in references if r != deleted_path]
            changed = True

        if changed or content != doc.content:
            doc.metadata["updated"] = str(date.today())
            post = frontmatter.Post(content, **doc.metadata)
            ref_full.write_text(frontmatter.dumps(post), encoding="utf-8")
            with self._lock:
                self._index_one_unlocked(ref_full)
                self._db.execute(
                    "INSERT OR REPLACE INTO file_mtime(path, mtime) VALUES (?,?)",
                    (ref_path, ref_full.stat().st_mtime),
                )
                self._db.commit()

    @staticmethod
    def _link_variants(from_path: str, to_path: str) -> list[str]:
        """Return possible link forms for *to_path* as seen from *from_path*."""
        variants = [to_path]
        try:
            from_dir = Path(from_path).parent
            rel = Path(to_path).relative_to(from_dir) if to_path.startswith(str(from_dir)) else None
            if rel:
                variants.append(str(rel))
        except (ValueError, TypeError):
            pass
        # Relative from same wiki subtree
        try:
            rel = str(Path(to_path).relative_to(Path(from_path).parent))
            if rel not in variants:
                variants.append(rel)
        except ValueError:
            pass
        # "../" relative
        try:
            from_parts = Path(from_path).parent.parts
            to_parts = Path(to_path).parts
            common = 0
            for a, b in zip(from_parts, to_parts):
                if a == b:
                    common += 1
                else:
                    break
            ups = len(from_parts) - common
            rel = '/'.join(['..'] * ups + list(to_parts[common:]))
            if rel not in variants:
                variants.append(rel)
        except Exception:
            pass
        return variants

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

        with self._lock:
            rows = self._db.execute(sql, params).fetchall()

        # FTS5 has no UNIQUE constraint — deduplicate by path, keep first occurrence
        seen: set[str] = set()
        result = []
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0])
                result.append({"path": r[0], "title": r[1], "category": r[2], "tags": r[3]})
        return result

    def related(self, path: str, depth: int = 2) -> list[str]:
        """Traverse reference chains up to the given depth."""
        with self._lock:
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

    def doc_title_category(self, path: str) -> tuple[str, str]:
        """Return (title, category) for a path from the FTS index (thread-safe)."""
        with self._lock:
            row = self._db.execute(
                "SELECT title, category FROM docs WHERE path=?", (path,)
            ).fetchone()
        if not row:
            return "", ""
        return row[0] if row[0] else "", row[1] if row[1] else ""
