"""Language normalization and localized file resolution for markdown assets."""

from __future__ import annotations

from pathlib import Path

__all__ = ["normalize_language", "pick_localized_markdown", "resolve_task_template_localized"]


def normalize_language(value: str | None) -> str:
    """Return 'de' or 'en' (default)."""
    if not value:
        return "en"
    v = str(value).strip().lower()
    if v.startswith("de"):
        return "de"
    return "en"


def pick_localized_markdown(base: Path, language: str | None) -> Path:
    """If language is German and ``<stem>.de.md`` exists next to canonical ``<stem>.md``, return it.

    *base* is the canonical English path, e.g. ``.../wiki-lint.md`` (not ``wiki-lint.de.md``).
    """
    lang = normalize_language(language)
    base = Path(base)
    if lang == "de":
        de_path = base.with_name(base.stem + ".de.md")
        if de_path.is_file():
            return de_path
    return base


def resolve_task_template_localized(
    raw: str | dict[str, str] | None,
    language: str | None,
) -> str:
    """Resolve pipeline step task_template: plain string or ``{en: ..., de: ...}``."""
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        lang = normalize_language(language)
        if lang == "de" and raw.get("de"):
            return str(raw["de"])
        if raw.get("en"):
            return str(raw["en"])
        if raw.get("de"):
            return str(raw["de"])
        return next((str(v) for v in raw.values() if v), "")
    return str(raw)
