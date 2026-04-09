"""Web research — URL scraping and search engine integration.

Two capabilities:
  - web_search: Web search via configurable backends (Brave, SearXNG)
  - fetch_url: Load a single URL and extract the main content as plain text

Uses trafilatura for robust article extraction and httpx as the HTTP client.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
import trafilatura

from core.capabilities import Capability

log = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30
_MAX_CONTENT_CHARS = 15_000
_USER_AGENT = "DorschAgent/1.0 (Business Research Bot)"


# ======================================================================
# URL extraction
# ======================================================================

def _extract_page(url: str, focus: str | None = None) -> dict[str, Any]:
    """Fetch a URL and extract the main content."""
    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return {"error": f"HTTP error: {exc}", "url": url}

    extracted = trafilatura.extract(
        resp.text,
        include_tables=True,
        include_links=True,
        output_format="txt",
    )
    if not extracted:
        return {"error": "No content could be extracted", "url": url}

    if len(extracted) > _MAX_CONTENT_CHARS:
        extracted = extracted[:_MAX_CONTENT_CHARS] + "\n\n[... truncated]"

    title = ""
    meta_xml = trafilatura.extract(
        resp.text,
        output_format="xmltei",
        include_tables=False,
    )
    if meta_xml:
        m = re.search(r"<title[^>]*>([^<]+)</title>", meta_xml)
        if m:
            title = m.group(1).strip()

    return {
        "url": url,
        "title": title,
        "content": extracted,
        "length": len(extracted),
    }


def _handle_fetch_url(args: dict) -> str:
    result = _extract_page(args["url"], focus=args.get("focus"))
    return json.dumps(result, ensure_ascii=False)


# ======================================================================
# Web search
# ======================================================================

def _search_brave(query: str, count: int = 5) -> list[dict]:
    """Brave Search API (free tier: 2000 requests/month)."""
    api_key = os.getenv("BRAVE_API_KEY", "")
    if not api_key:
        return [{"error": "BRAVE_API_KEY not set"}]

    resp = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": count},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("web", {}).get("results", [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
        })
    return results


def _search_searxng(query: str, count: int = 5) -> list[dict]:
    """SearXNG instance (self-hosted or public)."""
    instance = os.getenv("SEARXNG_URL", "")
    if not instance:
        return [{"error": "SEARXNG_URL not set"}]

    resp = httpx.get(
        f"{instance.rstrip('/')}/search",
        params={"q": query, "format": "json", "pageno": 1},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("results", [])[:count]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        })
    return results


def _handle_web_search(args: dict) -> str:
    query = args["query"]
    count = args.get("count", 5)

    if os.getenv("BRAVE_API_KEY"):
        results = _search_brave(query, count)
    elif os.getenv("SEARXNG_URL"):
        results = _search_searxng(query, count)
    else:
        return json.dumps(
            {"error": "No search backend configured. Set BRAVE_API_KEY or SEARXNG_URL."},
            ensure_ascii=False,
        )

    return json.dumps(results, ensure_ascii=False)


# ======================================================================
# Capability definitions
# ======================================================================

web_search = Capability(
    name="web_search",
    description="Search the internet for a query. Returns title, URL, and text snippet for each result.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term(s)"},
            "count": {"type": "integer", "description": "Number of results (default: 5)"},
        },
        "required": ["query"],
    },
    handler=_handle_web_search,
)

fetch_url = Capability(
    name="fetch_url",
    description="Fetch a web page and extract the main text content. Useful for reading articles, blog posts, company pages, or press releases.",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "focus": {"type": "string", "description": "Optional: what to focus on when extracting"},
        },
        "required": ["url"],
    },
    handler=_handle_fetch_url,
)
