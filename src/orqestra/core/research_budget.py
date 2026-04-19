"""Per-job budget and deduplication for `web_search` (Brave / SearXNG) calls."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

# Must stay aligned with orqestra.capabilities.research._handle_web_search clamps.
_MAX_QUERY_CHARS = 160
_MIN_COUNT = 1
_MAX_COUNT = 10


def _clamp_count(raw: Any) -> int:
    try:
        c = int(raw)
    except (TypeError, ValueError):
        c = 5
    return max(_MIN_COUNT, min(c, _MAX_COUNT))


def _normalize_query(q: Any) -> str:
    s = str(q or "").strip()[:_MAX_QUERY_CHARS]
    s = " ".join(s.split())
    return s.lower()


def normalize_web_search_args(fn_args: dict[str, Any]) -> tuple[str, int]:
    """Same normalization as :func:`_handle_web_search` (query + count clamp)."""
    q = _normalize_query(fn_args.get("query"))
    c = _clamp_count(fn_args.get("count", 5))
    return q, c


def cache_key_for_web_search(fn_args: dict[str, Any]) -> str:
    """Stable key for deduplication (same as post-normalization handler input)."""
    q, c = normalize_web_search_args(fn_args)
    return f"{q}|{c}"


@dataclass
class ResearchBudget:
    """Limit `web_search` calls per background job and cache identical queries."""

    max_web_search: int = 30
    used: int = 0
    cache: dict[str, str] = field(default_factory=dict)

    def consume(
        self,
        fn_name: str,
        fn_args: dict[str, Any],
    ) -> tuple[Literal["allow", "cache", "exhausted"], str | None]:
        """Decide whether to run `web_search`, return cache, or block (budget exhausted).

        Returns ``(kind, payload)`` where *payload* is set for ``cache`` and ``exhausted``
        (JSON string to send as tool result). For ``allow``, *payload* is ``None``.
        """
        if fn_name != "web_search":
            return "allow", None

        key = cache_key_for_web_search(fn_args)
        if not key.split("|", 1)[0]:
            # Empty query — let handler return empty_query error (still counts as one
            # attempt if we allowed; budget: allow once then handler errors)
            if self.used >= self.max_web_search:
                return "exhausted", _budget_error_payload(self.used, self.max_web_search)
            return "allow", None

        if key in self.cache:
            cached = self.cache[key]
            wrapped = _wrap_cache_hit(cached)
            return "cache", wrapped

        if self.used >= self.max_web_search:
            return "exhausted", _budget_error_payload(self.used, self.max_web_search)

        return "allow", None

    def store(self, fn_name: str, fn_args: dict[str, Any], result_json: str) -> None:
        """Cache successful handler output for ``web_search`` (same key as ``consume``)."""
        if fn_name != "web_search":
            return
        key = cache_key_for_web_search(fn_args)
        if not key.split("|", 1)[0]:
            return
        self.cache[key] = result_json

    def record_successful_search(self) -> None:
        """Call once after a real ``web_search`` handler invocation (not cache hit)."""
        self.used += 1


def _wrap_cache_hit(cached_json: str) -> str:
    """Prepend cache hint for the LLM."""
    try:
        parsed = json.loads(cached_json)
    except json.JSONDecodeError:
        return json.dumps(
            {"cache": "hit", "results": cached_json},
            ensure_ascii=False,
        )
    return json.dumps({"cache": "hit", "results": parsed}, ensure_ascii=False)


def _budget_error_payload(used: int, max_web: int) -> str:
    return json.dumps(
        {
            "error": "budget_exhausted",
            "used": used,
            "max": max_web,
            "message": (
                "Web search budget for this job is exhausted. Use kb_search/kb_read "
                "or fetch_url for known domains; do not retry with similar queries."
            ),
        },
        ensure_ascii=False,
    )


def web_search_result_counts_toward_budget(result_json: str) -> bool:
    """True if the handler actually invoked the search backend (Brave/SearXNG)."""
    try:
        obj: Any = json.loads(result_json)
    except json.JSONDecodeError:
        return True
    if isinstance(obj, dict):
        err = obj.get("error")
        if err == "empty_query":
            return False
        if isinstance(err, str) and "No search backend configured" in err:
            return False
        return True
    if isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], dict):
        err = obj[0].get("error")
        if err == "BRAVE_API_KEY not set":
            return False
        if err == "SEARXNG_URL not set":
            return False
    return True
