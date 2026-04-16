"""Knowledge base — Three-layer Markdown wiki with YAML frontmatter and FTS5 search.

Architecture:
    raw/          Immutable source documents (articles, PDFs, notes)
    wiki/         Structured, interlinked wiki pages (ergebnisse, recherche, wissen, akteure)

All .md files are indexed recursively. A SQLite FTS5 index provides fast
full-text search. Cross-references are tracked both from YAML `sources` fields
and from inline Markdown links [text](path.md).

Implementation is split across ``kb_index``, ``kb_crud``, and ``kb_fts``;
this module re-exports the composed ``KnowledgeBase`` / ``KnowledgeBaseCore``.
"""

from __future__ import annotations

from orqestra.capabilities.kb_crud import KnowledgeBaseCrudMixin
from orqestra.capabilities.kb_fts import (
    _build_fts_or_query,
    _fts5_prefix_term,
    _normalize_metadata,
    _tokenize_search_query,
)
from orqestra.capabilities.kb_index import KnowledgeBaseIndexMixin


class KnowledgeBaseCore(KnowledgeBaseIndexMixin, KnowledgeBaseCrudMixin):
    """Core FTS/wiki implementation."""


class KnowledgeBase(KnowledgeBaseCore):
    """In-process Markdown wiki backed by a persistent SQLite FTS5 search index."""

    pass


__all__ = [
    "KnowledgeBase",
    "KnowledgeBaseCore",
    "_build_fts_or_query",
    "_fts5_prefix_term",
    "_normalize_metadata",
    "_tokenize_search_query",
]
