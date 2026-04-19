"""Wiki dashboard, tree, read, search, graph, topic clusters."""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from orqestra.api.state import check_auth, state

if TYPE_CHECKING:
    from orqestra.capabilities.knowledge import KnowledgeBase

router = APIRouter()

_WIKI_HIDDEN_PATHS = {"wiki/memory.md", "wiki/log.md", "wiki/index.md"}


def sync_department_links() -> None:
    """Populate main_kb.department_links from the registry (labels, counts, index path)."""
    if not getattr(state, "main_kb", None) or not getattr(state, "registry", None):
        return
    links: list[dict[str, Any]] = []
    for name, dept in state.registry.items():
        kb = dept.kb
        entries = kb.list_entries()
        wiki_entries = [
            e for e in entries
            if e["path"].startswith("wiki/") and e["path"] not in _WIKI_HIDDEN_PATHS
        ]
        tree = wiki_tree_for_kb(kb, dept.label)
        index_path = tree.get("index_path") or "wiki/index.md"
        categories: dict[str, int] = {}
        for e in wiki_entries:
            c = e.get("category") or "uncategorized"
            categories[c] = categories.get(c, 0) + 1
        top = sorted(categories.items(), key=lambda x: (-x[1], x[0]))[:3]
        top_str = ", ".join(f"{k} ({v})" for k, v in top) if top else ""
        latest_path: str | None = None
        latest_title: str | None = None
        best_ts = ""
        for e in wiki_entries:
            doc = kb.read(e["path"])
            meta = doc.get("metadata") or {}
            u = str(meta.get("updated", "") or meta.get("created", ""))
            title = str(meta.get("title") or e.get("title") or Path(e["path"]).stem)
            if u >= best_ts:
                best_ts = u
                latest_path = e["path"]
                latest_title = title
        links.append({
            "name": name,
            "label": dept.label,
            "page_count": len(wiki_entries),
            "index_path": index_path,
            "top_categories": top_str,
            "recent_path": latest_path,
            "recent_title": latest_title,
        })
    state.main_kb.department_links = links


def wiki_tree_for_kb(kb: "KnowledgeBase", label: str) -> dict:
    """Build a tree of wiki/* entries from a KnowledgeBase instance."""
    entries = kb.list_entries()
    folders: dict[str, list[dict]] = {}
    index_path: str | None = None

    for e in entries:
        path = e["path"]
        parts = path.split("/")
        if not parts or parts[0] != "wiki":
            continue
        if path in _WIKI_HIDDEN_PATHS:
            if path == "wiki/index.md":
                index_path = path
            continue
        title = e["title"] or Path(path).stem
        item = {"path": path, "title": title, "category": e["category"]}

        if len(parts) == 2:
            folders.setdefault("_root", []).append(item)
        else:
            subfolder = parts[1]
            folders.setdefault(subfolder, []).append(item)

    for v in folders.values():
        v.sort(key=lambda x: x["title"].lower())

    return {"label": label, "folders": folders, "index_path": index_path}


@router.get("/api/wiki/home")
def wiki_home(request: Request):
    """Dashboard data for the wiki start page."""
    from orqestra.capabilities.knowledge import KnowledgeBase

    check_auth(request)

    def _section_stats(kb: KnowledgeBase) -> dict:
        entries = kb.list_entries()
        wiki_entries = [e for e in entries if e["path"].startswith("wiki/") and e["path"] not in _WIKI_HIDDEN_PATHS]
        categories: dict[str, int] = {}
        for e in wiki_entries:
            cat = e["category"] or "Sonstiges"
            categories[cat] = categories.get(cat, 0) + 1
        return {"page_count": len(wiki_entries), "categories": categories}

    def _recent_pages(kb: KnowledgeBase, dept_name: str | None, dept_label: str, limit: int = 5) -> list[dict]:
        entries = kb.list_entries()
        wiki_entries = [e for e in entries if e["path"].startswith("wiki/") and e["path"] not in _WIKI_HIDDEN_PATHS]
        pages: list[dict] = []
        for e in wiki_entries:
            doc = kb.read(e["path"])
            meta = doc.get("metadata", {})
            pages.append({
                "path": e["path"],
                "title": e["title"] or Path(e["path"]).stem,
                "category": e["category"],
                "updated": str(meta.get("updated", "")),
                "department": dept_name,
                "department_label": dept_label,
            })
        pages.sort(key=lambda p: p["updated"], reverse=True)
        return pages[:limit]

    main_stats = _section_stats(state.main_kb)
    recent: list[dict] = _recent_pages(state.main_kb, None, "Hauptwiki", limit=5)

    personal_section: dict[str, Any] | None = None
    if state.personal_kb is not None:
        pstats = _section_stats(state.personal_kb)
        personal_section = {
            "label": "Mein Wissen",
            "page_count": pstats["page_count"],
            "categories": pstats["categories"],
        }
        recent.extend(_recent_pages(state.personal_kb, "__personal__", "Mein Wissen", limit=5))

    dept_sections: list[dict] = []
    for dept_name, dept in state.registry.items():
        stats = _section_stats(dept.kb)
        dept_sections.append({
            "name": dept_name,
            "label": dept.label,
            "page_count": stats["page_count"],
            "categories": stats["categories"],
        })
        recent.extend(_recent_pages(dept.kb, dept_name, dept.label, limit=3))

    recent.sort(key=lambda p: p["updated"], reverse=True)

    out: dict[str, Any] = {
        "main": {
            "label": "Hauptwiki",
            "page_count": main_stats["page_count"],
            "categories": main_stats["categories"],
        },
        "departments": dept_sections,
        "recent": recent[:10],
    }
    if personal_section is not None:
        out["personal"] = personal_section
    return out


@router.get("/api/wiki/tree")
def wiki_tree(request: Request):
    """File tree of main wiki + all department wikis."""
    check_auth(request)
    result: dict[str, Any] = {
        "main": wiki_tree_for_kb(state.main_kb, "Hauptwiki"),
        "departments": {},
    }
    if state.personal_kb is not None:
        result["personal"] = wiki_tree_for_kb(state.personal_kb, "Mein Wissen")
    for dept_name, dept in state.registry.items():
        result["departments"][dept_name] = wiki_tree_for_kb(dept.kb, dept.label)
    return result


@router.get("/api/wiki/read")
def wiki_read(request: Request, path: str, department: str | None = None):
    """Read a single wiki page (markdown + frontmatter)."""
    check_auth(request)
    if department == "__personal__":
        if state.personal_kb is None:
            raise HTTPException(404, "Personal wiki is disabled")
        data = state.personal_kb.read(path)
    elif department:
        dept = state.registry.get(department)
        if not dept:
            raise HTTPException(404, f"Unknown department: {department}")
        data = dept.kb.read(path)
    else:
        data = state.main_kb.read(path)
    if "error" in data:
        raise HTTPException(404, data["error"])
    meta = data.get("metadata", {})
    content = data.get("content", "")

    def _wiki_link(m: re.Match) -> str:
        p = m.group(1)
        label = p.split("/")[-1]
        if label.endswith(".md"):
            label = label[:-3]
        label = label.replace("-", " ").replace("_", " ")
        return f"[{label}]({p})"

    content = re.sub(r"\[\[([^\]]+?\.md)\]\]", _wiki_link, content)
    out: dict[str, Any] = {
        "path": data["path"],
        "title": meta.get("title", ""),
        "category": meta.get("category", ""),
        "tags": meta.get("tags", []),
        "created": str(meta.get("created", "")),
        "updated": str(meta.get("updated", "")),
        "content": content,
    }
    if meta.get("job_id"):
        out["job_id"] = str(meta["job_id"])
    jr = meta.get("job_role")
    if jr is not None:
        out["job_role"] = str(jr).strip().lower()
    return out


# Strip every markdown link whose target is NOT an external http(s) URL.
# This keeps external references clickable in the PDF but renders
# wiki-internal cross-links (`[foo](foo.md)`, `[foo](../bar.md)`) as plain text.
_INTERNAL_LINK_RE = re.compile(r"\[([^\]]+)\]\((?!https?://)[^)]+\)")


def _slugify(text: str) -> str:
    """Filesystem-safe slug for the PDF filename."""
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s-]+", "-", text)
    return text or "page"


def _render_pdf_html(page: dict[str, Any]) -> str:
    """Turn a wiki page dict (as returned by ``/wiki/read``) into print-ready HTML."""
    import markdown as md  # local import so the module stays importable without the dep

    raw = page.get("content") or ""
    # `wiki_read` has already turned `[[foo.md]]` into `[foo](foo.md)`; strip every
    # markdown link whose target is not an external http(s) URL so wiki cross-links
    # show up as plain text in the PDF.
    raw = _INTERNAL_LINK_RE.sub(r"\1", raw)

    body_html = md.markdown(
        raw,
        extensions=["extra", "sane_lists", "tables", "fenced_code"],
        output_format="html5",
    )

    title = page.get("title") or page.get("path") or "Wiki"
    category = page.get("category") or ""
    updated = page.get("updated") or ""
    tags = page.get("tags") or []
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
    meta_bits: list[str] = []
    if category:
        meta_bits.append(f'<span>{category}</span>')
    if updated:
        meta_bits.append(f'<span>Aktualisiert: {updated}</span>')
    meta_html = " · ".join(meta_bits)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{ size: A4; margin: 22mm 20mm; }}
  html, body {{ font-family: "Helvetica", "Arial", sans-serif; color: #1f2328; font-size: 11pt; line-height: 1.55; }}
  body {{ margin: 0; }}
  h1.doc-title {{ font-size: 22pt; margin: 0 0 6pt; color: #0f172a; }}
  .doc-meta {{ color: #64748b; font-size: 9.5pt; margin-bottom: 2pt; }}
  .doc-tags {{ margin: 6pt 0 18pt; }}
  .doc-tags .tag {{
    display: inline-block; font-size: 8.5pt; padding: 1pt 6pt; margin-right: 4pt;
    border: 1px solid #cbd5e1; border-radius: 999px; color: #475569;
  }}
  hr.doc-sep {{ border: none; border-top: 1px solid #e2e8f0; margin: 0 0 18pt; }}
  h1, h2, h3, h4, h5, h6 {{ color: #0f172a; margin-top: 14pt; margin-bottom: 6pt; line-height: 1.25; }}
  h1 {{ font-size: 17pt; }} h2 {{ font-size: 14pt; }} h3 {{ font-size: 12pt; }}
  h4, h5, h6 {{ font-size: 11pt; }}
  p {{ margin: 0 0 8pt; }}
  ul, ol {{ margin: 0 0 8pt 18pt; padding: 0; }}
  li {{ margin-bottom: 3pt; }}
  a {{ color: #2563eb; text-decoration: none; }}
  code {{ font-family: "Menlo", "Consolas", monospace; font-size: 9.5pt;
          background: #f1f5f9; padding: 1pt 4pt; border-radius: 3pt; }}
  pre {{ background: #f1f5f9; padding: 8pt 10pt; border-radius: 4pt;
         overflow: auto; font-size: 9.5pt; page-break-inside: avoid; }}
  pre code {{ background: transparent; padding: 0; }}
  blockquote {{ margin: 0 0 8pt; padding: 4pt 10pt; border-left: 3px solid #cbd5e1;
                color: #475569; background: #f8fafc; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0 0 10pt; font-size: 10pt; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 4pt 6pt; text-align: left; vertical-align: top; }}
  th {{ background: #f1f5f9; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
  <h1 class="doc-title">{title}</h1>
  {f'<div class="doc-meta">{meta_html}</div>' if meta_html else ''}
  {f'<div class="doc-tags">{tags_html}</div>' if tags_html else ''}
  <hr class="doc-sep">
  <article>{body_html}</article>
</body>
</html>
"""


@router.get("/api/wiki/export/pdf")
def wiki_export_pdf(request: Request, path: str, department: str | None = None):
    """Render a single wiki page as a downloadable PDF (WeasyPrint)."""
    check_auth(request)
    try:
        from weasyprint import HTML  # local import: heavy dep, only needed here
    except ImportError as exc:  # pragma: no cover - informative runtime message
        raise HTTPException(
            500,
            "PDF export requires WeasyPrint. Install it with `pip install weasyprint` "
            "and make sure the native Pango/Cairo libraries are available.",
        ) from exc

    page = wiki_read(request, path, department)
    html = _render_pdf_html(page)
    pdf_bytes = HTML(string=html).write_pdf()

    filename = f"{_slugify(page.get('title') or Path(path).stem)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/api/wiki/delete")
def wiki_delete(request: Request, path: str, department: str | None = None):
    """Delete a wiki page and clean up all cross-references."""
    check_auth(request)
    if department == "__personal__":
        if state.personal_kb is None:
            raise HTTPException(400, "Personal wiki is disabled")
        result = state.personal_kb.delete(path)
    elif department:
        dept = state.registry.get(department)
        if not dept:
            raise HTTPException(404, f"Unknown department: {department}")
        result = dept.kb.delete(path)
    else:
        result = state.main_kb.delete(path)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/api/wiki/ingest")
async def wiki_ingest(
    request: Request,
    file: UploadFile = File(...),
    department: str | None = Form(default=None),
):
    """Upload a document into raw/docs/ and start a background wiki-ingest job."""
    check_auth(request)

    raw_name = file.filename or "upload"
    safe_base = Path(raw_name).name
    if not safe_base or safe_base in (".", ".."):
        safe_base = "upload.bin"

    dept_str = (department or "").strip() or None
    if dept_str == "__personal__":
        if state.personal_kb is None:
            raise HTTPException(400, "Personal wiki is disabled")
        kb = state.personal_kb
    elif dept_str:
        dept = state.registry.get(dept_str)
        if not dept:
            raise HTTPException(400, f"Unknown department: {dept_str}")
        kb = dept.kb
    else:
        kb = state.main_kb

    unique = f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_base}"
    docs_dir = kb.base / "raw" / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    save_path = docs_dir / unique

    content = await file.read()
    save_path.write_bytes(content)

    try:
        from orqestra.capabilities.files import extract_text

        text = extract_text(save_path)
    except ValueError as exc:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    rel_raw = f"raw/docs/{unique}"
    if dept_str == "__personal__":
        task = (
            f"[Mein Wissen — Import: {safe_base}]\n\n"
            f"{text}\n\n"
            f"---\n"
            f"Verarbeite dieses Dokument gemäß dem Skill **wiki-ingest**. "
            f"WICHTIG: Verwende ausschließlich **`my_kb_write`** (nicht `kb_write`), "
            f"da dieses Dokument ins persönliche Wiki „Mein Wissen“ gehört. "
            f"Zum Suchen nutze **`kb_search`** (durchsucht Hauptwiki und Mein Wissen). "
            f"Speichere die Rohquelle ggf. als `raw/articles/YYYY-MM-DD-Titel.md` in dieser KB. "
            f"Original-Upload: `{rel_raw}`.\n"
        )
        job = state.registry.submit_main_wiki_ingest(task)
    else:
        task = (
            f"[Firmenwissen-Import: {safe_base}]\n\n"
            f"{text}\n\n"
            f"---\n"
            f"Verarbeite dieses Dokument gemäß dem Skill **wiki-ingest** (Skills im Skills-Ordner). "
            f"Speichere die unveränderte Rohquelle zusätzlich als `raw/articles/YYYY-MM-DD-Titel.md` in "
            f"dieser Knowledge Base, falls sie nicht bereits dort liegt. Alle Pfade beziehen sich auf "
            f"die Knowledge Base dieses Jobs. "
            f"Das hochgeladene Original liegt unter `{rel_raw}`. "
            f"Falls der Text oben gekürzt ist (sehr große Dateien), arbeite mit dem Vorhandenen und "
            f"verweise auf das Original unter `{rel_raw}`.\n"
        )
        if dept_str:
            job = state.registry.submit_job(dept_str, task, mode="single")
        else:
            job = state.registry.submit_main_wiki_ingest(task)

    return {
        "job_id": job.id,
        "filename": safe_base,
        "department": dept_str,
    }


@router.get("/api/wiki/search")
def wiki_search(request: Request, q: str, limit: int = 20):
    """Full-text search across main wiki + all department wikis."""
    check_auth(request)
    results: list[dict] = []
    main_hits, _ = state.main_kb.search(q, limit=limit)
    for hit in main_hits:
        hit["department"] = None
        hit["department_label"] = "Hauptwiki"
        results.append(hit)

    if state.personal_kb is not None:
        pers_hits, _ = state.personal_kb.search(q, limit=limit)
        for hit in pers_hits:
            hit["department"] = "__personal__"
            hit["department_label"] = "Mein Wissen"
            results.append(hit)

    for dept_name, dept in state.registry.items():
        dept_hits, _ = dept.kb.search(q, limit=limit)
        for hit in dept_hits:
            hit["department"] = dept_name
            hit["department_label"] = dept.label
            results.append(hit)

    return results[:limit]


_GENERIC_TAGS = frozenset({
    "ki", "ai", "analyse", "recherche", "ergebnis", "zusammenfassung",
    "deutsch", "german", "content", "wiki", "dach",
})

_FOLDER_LABELS: dict[str, str] = {
    "ergebnisse": "Ergebnisse",
    "recherche": "Recherche",
    "wissen": "Wissen",
    "akteure": "Akteure",
    "drafts": "Entwürfe",
    "_root": "Allgemein",
}


def _cluster_pages(kb: "KnowledgeBase") -> dict:
    """Build topic clusters from a knowledge base using tags and job_id."""
    entries = kb.list_entries()
    wiki_entries = [
        e for e in entries
        if e["path"].startswith("wiki/") and e["path"] not in _WIKI_HIDDEN_PATHS
    ]

    meta_map: dict[str, dict] = {}
    with kb._lock:
        meta_rows = kb._db.execute("SELECT path, raw_yaml FROM meta").fetchall()
    for mpath, raw_yaml in meta_rows:
        if raw_yaml:
            try:
                parsed = json.loads(raw_yaml) if raw_yaml.startswith("{") else yaml.safe_load(raw_yaml)
                if isinstance(parsed, dict):
                    meta_map[mpath] = parsed
            except Exception:
                pass

    pages: list[dict[str, Any]] = []
    for e in wiki_entries:
        fm = meta_map.get(e["path"], {})
        tags_raw = fm.get("tags") or []
        if isinstance(tags_raw, str):
            tags_raw = tags_raw.split()
        tags = [t.strip().lower() for t in tags_raw if t.strip()]
        parts = e["path"].split("/")
        folder = parts[1] if len(parts) > 2 else "_root"
        pages.append({
            "path": e["path"],
            "title": e["title"] or Path(e["path"]).stem,
            "category": e["category"],
            "tags": tags,
            "folder": folder,
            "folder_label": _FOLDER_LABELS.get(folder, folder.replace("-", " ").replace("_", " ").title()),
            "job_id": str(fm.get("job_id", "")),
            "job_role": str(fm.get("job_role", "")).strip().lower(),
            "updated": str(fm.get("updated", "") or fm.get("created", "")),
        })

    tag_counts: Counter[str] = Counter()
    for p in pages:
        for t in p["tags"]:
            if t not in _GENERIC_TAGS:
                tag_counts[t] += 1

    cluster_tags = {t for t, c in tag_counts.items() if c >= 2}

    total = len(pages)
    if total > 0:
        cluster_tags = {t for t in cluster_tags if tag_counts[t] / total < 0.6}

    page_cluster: dict[str, str] = {}
    for p in pages:
        specific = [t for t in p["tags"] if t in cluster_tags]
        if specific:
            best = min(specific, key=lambda t: tag_counts[t])
            page_cluster[p["path"]] = best

    job_clusters: dict[str, str] = {}
    job_groups: dict[str, list[dict]] = {}
    for p in pages:
        jid = p["job_id"]
        if jid:
            job_groups.setdefault(jid, []).append(p)
    for jid, group in job_groups.items():
        assigned = [page_cluster[p["path"]] for p in group if p["path"] in page_cluster]
        if assigned:
            dominant = Counter(assigned).most_common(1)[0][0]
            job_clusters[jid] = dominant

    for p in pages:
        if p["path"] not in page_cluster and p["job_id"] in job_clusters:
            page_cluster[p["path"]] = job_clusters[p["job_id"]]

    clusters: dict[str, list[dict]] = {}
    unclustered: list[dict] = []
    for p in pages:
        tag = page_cluster.get(p["path"])
        if tag:
            clusters.setdefault(tag, []).append(p)
        else:
            unclustered.append(p)

    result_clusters: list[dict] = []
    for tag, cpages in sorted(clusters.items(), key=lambda x: -len(x[1])):
        deliverable = next((p for p in cpages if p["job_role"] == "deliverable"), None)
        label = deliverable["title"] if deliverable else tag.replace("-", " ").replace("_", " ").title()
        folders_in_cluster = sorted({p["folder_label"] for p in cpages})
        cpages.sort(key=lambda p: (0 if p["job_role"] == "deliverable" else 1, p["title"].lower()))
        result_clusters.append({
            "label": label,
            "tag": tag,
            "page_count": len(cpages),
            "folders": folders_in_cluster,
            "has_deliverable": deliverable is not None,
            "pages": cpages,
        })

    unclustered.sort(key=lambda p: p["title"].lower())

    return {"clusters": result_clusters, "unclustered": unclustered}


@router.get("/api/wiki/clusters")
def wiki_clusters(request: Request, department: str | None = None):
    """Topic clusters for a wiki (department, personal, or main)."""
    check_auth(request)
    if department == "__personal__":
        if state.personal_kb is None:
            raise HTTPException(404, "Personal wiki is disabled")
        kb = state.personal_kb
    elif department:
        dept = state.registry.get(department)
        if not dept:
            raise HTTPException(404, f"Unknown department: {department}")
        kb = dept.kb
    else:
        kb = state.main_kb
    return _cluster_pages(kb)


@router.get("/api/wiki/graph")
def wiki_graph(request: Request):
    """Nodes + edges for Obsidian-style graph view (only index-reachable pages)."""
    from orqestra.capabilities.knowledge import KnowledgeBase

    check_auth(request)

    nodes: list[dict] = []
    edges: list[dict] = []
    all_tags: dict[str, list[str]] = {}

    def _collect(kb: KnowledgeBase, dept_name: str | None, dept_label: str):
        prefix = f"{dept_name}::" if dept_name else ""

        with kb._lock:
            link_rows = kb._db.execute("SELECT source, target FROM links").fetchall()

        neighbours: dict[str, set[str]] = {}
        for src, tgt in link_rows:
            neighbours.setdefault(src, set()).add(tgt)
            neighbours.setdefault(tgt, set()).add(src)

        index_path = "wiki/index.md"
        reachable: set[str] = set()
        frontier = {index_path}
        while frontier:
            reachable |= frontier
            next_level: set[str] = set()
            for p in frontier:
                next_level |= neighbours.get(p, set())
            frontier = next_level - reachable

        meta_map: dict[str, dict] = {}
        with kb._lock:
            meta_rows = kb._db.execute("SELECT path, raw_yaml FROM meta").fetchall()
        for mpath, raw_yaml in meta_rows:
            if raw_yaml:
                try:
                    parsed = yaml.safe_load(raw_yaml)
                    if isinstance(parsed, dict):
                        meta_map[mpath] = parsed
                except Exception:
                    pass

        entries = kb.list_entries()
        for e in entries:
            if e["path"] not in reachable:
                continue
            node_id = f"{prefix}{e['path']}"
            tags = [t.strip() for t in (e.get("tags") or "").split() if t.strip()]
            fm = meta_map.get(e["path"], {})
            job_id = fm.get("job_id")
            job_role = fm.get("job_role")
            node: dict[str, Any] = {
                "id": node_id,
                "title": e["title"] or Path(e["path"]).stem,
                "department": dept_name,
                "department_label": dept_label,
                "category": e["category"],
                "tags": tags,
            }
            if job_id:
                node["job_id"] = str(job_id)
            if job_role:
                node["job_role"] = str(job_role).strip().lower()
            nodes.append(node)
            for tag in tags:
                all_tags.setdefault(tag, []).append(node_id)

        for src, tgt in link_rows:
            if src in reachable and tgt in reachable:
                edges.append({
                    "source": f"{prefix}{src}",
                    "target": f"{prefix}{tgt}",
                    "type": "link",
                })

    _collect(state.main_kb, None, "Hauptwiki")
    if state.personal_kb is not None:
        _collect(state.personal_kb, "__personal__", "Mein Wissen")
    for dept_name, dept in state.registry.items():
        _collect(dept.kb, dept_name, dept.label)

    node_ids_set = {n["id"] for n in nodes}
    valid_edges = [
        e for e in edges
        if e["source"] in node_ids_set and e["target"] in node_ids_set
    ]

    for tag, tag_node_ids in all_tags.items():
        if len(tag_node_ids) < 2 or len(tag_node_ids) > 10:
            continue
        for i in range(len(tag_node_ids)):
            for j in range(i + 1, len(tag_node_ids)):
                valid_edges.append({
                    "source": tag_node_ids[i],
                    "target": tag_node_ids[j],
                    "type": "tag",
                })

    job_groups: dict[str, list[dict]] = {}
    for n in nodes:
        jid = n.get("job_id")
        if jid:
            job_groups.setdefault(jid, []).append(n)
    for jid, group in job_groups.items():
        deliverables = [n for n in group if n.get("job_role") == "deliverable"]
        supporting = [n for n in group if n.get("job_role") != "deliverable"]
        if deliverables:
            target = deliverables[0]["id"]
            for s in supporting:
                valid_edges.append({
                    "source": s["id"],
                    "target": target,
                    "type": "job",
                })

    return {"nodes": nodes, "edges": valid_edges}
