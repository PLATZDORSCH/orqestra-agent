#!/usr/bin/env python3
"""One-time migration: wiki/players|sources|synthesis|topics|trends|regulation|market
-> wiki/akteure|recherche|ergebnisse|wissen (4 folders).

Run from repo root: python3 scripts/migrate_wiki_folders.py
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (old_subdir, new_subdir, new_category)
MOVES: list[tuple[str, str, str]] = [
    ("wiki/players", "wiki/akteure", "akteure"),
    ("wiki/sources", "wiki/recherche", "recherche"),
    ("wiki/synthesis", "wiki/ergebnisse", "ergebnisse"),
    ("wiki/topics", "wiki/wissen", "wissen"),
    ("wiki/trends", "wiki/wissen", "wissen"),
    ("wiki/regulation", "wiki/wissen", "wissen"),
    ("wiki/market", "wiki/wissen", "wissen"),
]

# Glob patterns for link replacement in markdown bodies
LINK_REPLACEMENTS: list[tuple[str, str]] = [
    ("wiki/players/", "wiki/akteure/"),
    ("wiki/sources/", "wiki/recherche/"),
    ("wiki/synthesis/", "wiki/ergebnisse/"),
    ("wiki/topics/", "wiki/wissen/"),
    ("wiki/trends/", "wiki/wissen/"),
    ("wiki/regulation/", "wiki/wissen/"),
    ("wiki/market/", "wiki/wissen/"),
]


def wiki_roots() -> list[Path]:
    out: list[Path] = []
    pk = ROOT / "personal_knowledge"
    if (pk / "wiki").is_dir():
        out.append(pk)
    kb = ROOT / "knowledge_base"
    if (kb / "wiki").is_dir():
        out.append(kb)
    for dept in (ROOT / "departments").iterdir():
        w = dept / "knowledge_base" / "wiki"
        if w.is_dir():
            out.append(dept / "knowledge_base")
    return out


def unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    for i in range(2, 1000):
        alt = dest.with_name(f"{stem}-dup{i}{suf}")
        if not alt.exists():
            return alt
    raise RuntimeError(f"Could not find unique name for {dest}")


def patch_category(content: str, new_cat: str) -> str:
    # category: foo -> category: new_cat
    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{new_cat}"

    return re.sub(
        r"^(category:\s*)([^\s#]+)",
        repl,
        content,
        count=1,
        flags=re.MULTILINE,
    )


def patch_links(content: str) -> str:
    for old, new in LINK_REPLACEMENTS:
        content = content.replace(old, new)
    return content


def migrate_kb_base(kb_base: Path) -> int:
    """Migrate wiki under kb_base (which contains wiki/ and possibly .fts_index.db). Returns file count moved."""
    wiki = kb_base / "wiki"
    if not wiki.is_dir():
        return 0
    moved = 0
    for old_rel, new_rel, new_cat in MOVES:
        old_dir = kb_base / old_rel
        if not old_dir.is_dir():
            continue
        new_parent = kb_base / new_rel
        new_parent.mkdir(parents=True, exist_ok=True)
        for f in sorted(old_dir.rglob("*.md")):
            rel_under_old = f.relative_to(old_dir)
            dest = new_parent / rel_under_old
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest = unique_dest(dest)
            text = f.read_text(encoding="utf-8")
            text = patch_category(text, new_cat)
            text = patch_links(text)
            dest.write_text(text, encoding="utf-8")
            f.unlink()
            moved += 1
        # remove old dir tree (bottom-up)
        for sub in sorted(old_dir.rglob("*"), reverse=True):
            if sub.is_file():
                continue
            try:
                sub.rmdir()
            except OSError:
                pass
        try:
            old_dir.rmdir()
        except OSError:
            pass
    return moved


def main() -> int:
    total = 0
    for base in wiki_roots():
        n = migrate_kb_base(base)
        if n:
            print(f"{base}: migrated {n} files")
            total += n
    print(f"Total files migrated: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
