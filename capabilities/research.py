"""Web research — URL scraping and search engine integration.

Capabilities:
  - web_search: Web search via configurable backends (Brave, SearXNG)
  - fetch_url: Load a URL and extract main text — **defaults to headless Chromium**
    (Playwright) so JavaScript-rendered content is included; optional raw HTTP fallback.

Uses trafilatura for article extraction and httpx as the HTTP fallback client.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
import trafilatura

from capabilities.browser_core import (
    DEFAULT_TIMEOUT_MS,
    DEFAULT_WAIT_UNTIL,
    fetch_rendered_html,
    playwright_available,
)
from core.capabilities import Capability

_HTTP_TIMEOUT = 30
_MAX_CONTENT_CHARS = 15_000
_USER_AGENT = "CodAgent/1.0 (Business Research Bot)"


def _trafilatura_from_html(
    html: str,
    source_url: str,
    final_url: str,
    *,
    render_mode: str,
    browser_error: str | None = None,
) -> dict[str, Any]:
    extracted = trafilatura.extract(
        html,
        include_tables=True,
        include_links=True,
        output_format="txt",
    )
    if not extracted:
        return {
            "error": "No content could be extracted",
            "url": source_url,
            "final_url": final_url,
            "render_mode": render_mode,
        }

    if len(extracted) > _MAX_CONTENT_CHARS:
        extracted = extracted[:_MAX_CONTENT_CHARS] + "\n\n[... truncated]"

    title = ""
    meta_xml = trafilatura.extract(
        html,
        output_format="xmltei",
        include_tables=False,
    )
    if meta_xml:
        m = re.search(r"<title[^>]*>([^<]+)</title>", meta_xml)
        if m:
            title = m.group(1).strip()

    out: dict[str, Any] = {
        "url": source_url,
        "final_url": final_url,
        "title": title,
        "content": extracted,
        "length": len(extracted),
        "render_mode": render_mode,
    }
    if browser_error:
        out["browser_error"] = browser_error
    return out


def _extract_page_http(url: str) -> tuple[str, str] | dict[str, Any]:
    """Return (html, final_url) or error dict."""
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

    return resp.text, str(resp.url)


def _extract_page(
    url: str,
    focus: str | None = None,
    *,
    use_browser: bool = True,
    wait_until: str | None = None,
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    """Fetch URL and extract main content. Prefer Playwright when available."""
    del focus  # reserved for future trafilatura tuning

    if wait_until is None:
        wait_until = DEFAULT_WAIT_UNTIL

    if timeout_ms is None:
        timeout_ms = DEFAULT_TIMEOUT_MS
    else:
        timeout_ms = int(timeout_ms)
    timeout_ms = max(5_000, min(timeout_ms, 120_000))

    html: str | None = None
    final_url = url
    render_mode = "http"
    browser_error: str | None = None

    if use_browser and playwright_available():
        r = fetch_rendered_html(url, wait_until=wait_until, timeout_ms=timeout_ms)
        if r.get("ok"):
            html = r["html"]
            final_url = r.get("final_url") or url
            render_mode = "chromium"
        else:
            browser_error = r.get("error", "browser render failed")
            render_mode = "http_fallback"
    elif use_browser and not playwright_available():
        render_mode = "http_no_playwright"

    if html is None:
        got = _extract_page_http(url)
        if isinstance(got, dict):
            got["render_mode"] = render_mode
            if browser_error:
                got["browser_error"] = browser_error
            return got
        html, final_url = got

    result = _trafilatura_from_html(
        html,
        source_url=url,
        final_url=final_url,
        render_mode=render_mode,
        browser_error=browser_error,
    )
    return result


def _handle_fetch_url(args: dict) -> str:
    use_browser = args.get("use_browser", True)
    if isinstance(use_browser, str):
        use_browser = use_browser.strip().lower() not in ("false", "0", "no", "")

    wait_until = args.get("wait_until") or DEFAULT_WAIT_UNTIL
    timeout_ms = args.get("timeout_ms")
    if timeout_ms is None:
        timeout_ms = DEFAULT_TIMEOUT_MS
    else:
        timeout_ms = int(timeout_ms)

    result = _extract_page(
        args["url"],
        focus=args.get("focus"),
        use_browser=use_browser,
        wait_until=wait_until,
        timeout_ms=timeout_ms,
    )
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
    description=(
        "Fetch a web page and extract the main text (articles, blogs, company pages). "
        "By default uses headless Chromium (Playwright) so client-rendered/SPA content is visible; "
        "falls back to plain HTTP if the browser is unavailable or fails. "
        "Default navigation wait is `load` (reliable); use `networkidle` only if a SPA needs it. "
        "Set use_browser=false only for static documents where you want raw HTML speed. "
        "For technical SEO metadata (meta, JSON-LD, canonical), use analyze_page_seo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"},
            "focus": {"type": "string", "description": "Optional: what to focus on when extracting"},
            "use_browser": {
                "type": "boolean",
                "description": "If true (default), render with Chromium when Playwright is installed",
            },
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "description": "Playwright navigation wait (default load). Ignored when use_browser=false.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Navigation timeout for browser fetch (default 45000)",
            },
        },
        "required": ["url"],
    },
    handler=_handle_fetch_url,
)
