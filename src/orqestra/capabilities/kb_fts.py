"""FTS5 query helpers and metadata normalization for the knowledge base."""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

# FTS5: stop words removed so OR + prefix matches broader (e.g. "KI" + "Autowerkstätten" separately).
_STOP_WORDS = frozenset({
    "in", "für", "und", "oder", "die", "der", "das", "den", "dem", "des",
    "ein", "eine", "einen", "einem", "einer", "eines", "von", "zu", "mit", "auf",
    "ist", "im", "an", "am", "als", "auch", "bei", "nach", "über", "unter",
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "is", "are",
})


def _tokenize_search_query(query: str) -> list[str]:
    """Split query into meaningful tokens; strip punctuation; drop stop words."""
    words: list[str] = []
    for raw in query.split():
        w = raw.strip('.,;:!?()[]"\'')
        if len(w) < 2:
            continue
        if w.lower() in _STOP_WORDS:
            continue
        words.append(w)
    if not words:
        for raw in query.split():
            w = raw.strip('.,;:!?()[]"\'')
            if w:
                words.append(w)
    return words


def _fts5_prefix_term(word: str) -> str:
    """Single token for FTS5 MATCH with prefix search; escape double quotes."""
    t = word.replace('"', '""').strip()
    if not t:
        return ""
    # Prefix: token* — quote if token has spaces or FTS-special chars
    if any(c in t for c in " \t\n\"-"):
        return f'"{t}"*'
    return f"{t}*"


def _build_fts_or_query(words: list[str]) -> str:
    parts = [_fts5_prefix_term(w) for w in words if _fts5_prefix_term(w)]
    if not parts:
        return ""
    return " OR ".join(parts)


def _normalize_metadata(metadata: Any) -> dict[str, Any]:
    """Ensure frontmatter metadata is a dict (LLMs sometimes pass a JSON string)."""
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str):
        s = metadata.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            log.debug("kb_write: metadata is not valid JSON, using empty dict")
        return {}
    log.warning("kb_write: metadata has unexpected type %s, using empty dict", type(metadata).__name__)
    return {}
