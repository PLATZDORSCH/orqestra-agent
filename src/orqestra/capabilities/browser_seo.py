"""Browser-based SEO analysis — Chromium via Playwright.

Renders pages with JavaScript (like a real browser), then reads DOM state for
meta tags, canonical, headings, and JSON-LD structured data. Shares session
setup with fetch_url via browser_core.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from orqestra.capabilities.browser_core import (
    DEFAULT_TIMEOUT_MS,
    DEFAULT_WAIT_UNTIL,
    playwright_available,
    playwright_page,
)
from orqestra.core.capabilities import Capability

log = logging.getLogger(__name__)

_MAX_JSON_LD_ITEMS = 20


def _analyze_with_browser(
    url: str,
    wait_until: str,
    timeout_ms: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {"url_requested": url}

    with playwright_page(url, wait_until=wait_until, timeout_ms=timeout_ms) as (page, response):
        result["http_status"] = response.status if response else None
        result["final_url"] = page.url

        data = page.evaluate(
            """() => {
  const meta = {};
  document.querySelectorAll('meta').forEach((m) => {
    const name =
      m.getAttribute('name') ||
      m.getAttribute('property') ||
      m.getAttribute('http-equiv');
    const content = m.getAttribute('content');
    if (!name || content == null) return;
    if (!meta[name]) meta[name] = [];
    meta[name].push(content);
  });

  const linkRels = {};
  document.querySelectorAll('link[rel]').forEach((l) => {
    const rel = (l.getAttribute('rel') || '').toLowerCase();
    const href = l.href || l.getAttribute('href');
    if (!href) return;
    const entry = {
      href,
      hreflang: l.getAttribute('hreflang') || null,
      type: l.getAttribute('type') || null,
    };
    if (!linkRels[rel]) linkRels[rel] = [];
    linkRels[rel].push(entry);
  });

  const headings = {};
  for (let i = 1; i <= 6; i++) {
    const tag = 'h' + i;
    headings[tag] = [...document.querySelectorAll(tag)]
      .map((h) => h.textContent.trim().replace(/\\s+/g, ' '))
      .filter(Boolean);
  }

  const jsonLd = [];
  document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
    const raw = s.textContent || '';
    try {
      jsonLd.push(JSON.parse(raw));
    } catch (e) {
      jsonLd.push({
        _parse_error: String(e),
        _snippet: raw.slice(0, 400),
      });
    }
  });

  const bodyText = (document.body && document.body.innerText) || '';
  const wordCount = bodyText.trim().length
    ? bodyText.trim().split(/\\s+/).filter(Boolean).length
    : 0;

  const htmlLang = document.documentElement.getAttribute('lang');
  const charsetEl = document.querySelector('meta[charset]');
  const contentTypeEl = document.querySelector('meta[http-equiv="Content-Type"]');
  const charset = charsetEl
    ? charsetEl.getAttribute('charset')
    : (contentTypeEl ? contentTypeEl.getAttribute('content') : null);

  return {
    document_title: document.title || '',
    meta,
    link_rels: linkRels,
    headings,
    json_ld: jsonLd,
    html_lang: htmlLang || null,
    charset: charset || null,
    word_count_visible: wordCount,
    has_noscript: !!document.querySelector('noscript'),
  };
}"""
        )
        result["page"] = data

    return result


def _summarize_json_ld(items: list[Any]) -> list[dict[str, Any]]:
    """Extract @type and @id from JSON-LD roots (including @graph nodes)."""
    out: list[dict[str, Any]] = []

    def extract(obj: Any) -> None:
        if isinstance(obj, dict):
            if "@graph" in obj:
                for node in obj["@graph"]:
                    extract(node)
                return
            if "@type" in obj:
                t = obj["@type"]
                entry: dict[str, Any] = {"@type": t}
                if obj.get("@id"):
                    entry["@id"] = obj["@id"]
                out.append(entry)
        elif isinstance(obj, list):
            for x in obj:
                extract(x)

    for item in items[:_MAX_JSON_LD_ITEMS]:
        extract(item)
    return out[:_MAX_JSON_LD_ITEMS]


def _detect_issues(page: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    title = (page.get("document_title") or "").strip()
    meta = page.get("meta") or {}

    def first(*keys: str) -> str:
        for k in keys:
            vals = meta.get(k)
            if vals and isinstance(vals, list) and vals[0]:
                return str(vals[0]).strip()
        return ""

    desc = first("description", "og:description")
    robots = " ".join(meta.get("robots", []) if meta.get("robots") else []).lower()

    if not title:
        issues.append(
            {"severity": "high", "code": "missing_title", "detail": "document.title is empty after render"}
        )
    elif len(title) < 15:
        issues.append(
            {"severity": "medium", "code": "title_short", "detail": f"Title is only {len(title)} characters"}
        )
    elif len(title) > 70:
        issues.append(
            {"severity": "low", "code": "title_long", "detail": f"Title is {len(title)} characters (often truncated in SERPs)"}
        )

    if not desc:
        issues.append(
            {"severity": "medium", "code": "missing_meta_description", "detail": "No meta name=description or og:description"}
        )
    elif len(desc) < 50:
        issues.append(
            {"severity": "low", "code": "meta_description_short", "detail": f"Meta description only {len(desc)} characters"}
        )
    elif len(desc) > 200:
        issues.append(
            {"severity": "low", "code": "meta_description_long", "detail": f"Meta description is {len(desc)} characters"}
        )

    h1s = page.get("headings", {}).get("h1", [])
    if len(h1s) == 0:
        issues.append(
            {"severity": "high", "code": "missing_h1", "detail": "No visible H1 in DOM after render"}
        )
    elif len(h1s) > 1:
        issues.append(
            {
                "severity": "medium",
                "code": "multiple_h1",
                "detail": f"{len(h1s)} H1 elements (prefer exactly one)",
            }
        )

    if "noindex" in robots:
        issues.append(
            {"severity": "high", "code": "robots_noindex", "detail": "meta robots contains noindex"}
        )

    json_ld = page.get("json_ld") or []
    parse_errors = [x for x in json_ld if isinstance(x, dict) and x.get("_parse_error")]
    for err in parse_errors:
        issues.append(
            {
                "severity": "medium",
                "code": "json_ld_parse_error",
                "detail": err.get("_parse_error", "invalid JSON-LD")[:200],
            }
        )

    og_title = first("og:title")
    if og_title and title and og_title != title:
        issues.append(
            {
                "severity": "low",
                "code": "og_title_mismatch",
                "detail": "og:title differs from document title",
            }
        )

    return issues


def _handle_analyze_page_seo(args: dict) -> str:
    if not playwright_available():
        return json.dumps(
            {
                "error": (
                    "Playwright is not installed. Install with: pip install playwright && "
                    "playwright install chromium"
                ),
            },
            ensure_ascii=False,
        )

    url = str(args["url"]).strip()
    if not url.startswith(("http://", "https://")):
        return json.dumps({"error": "URL must start with http:// or https://"}, ensure_ascii=False)

    wait_until = args.get("wait_until") or DEFAULT_WAIT_UNTIL
    if wait_until not in ("load", "domcontentloaded", "networkidle", "commit"):
        wait_until = DEFAULT_WAIT_UNTIL

    timeout_ms = int(args.get("timeout_ms") or DEFAULT_TIMEOUT_MS)
    timeout_ms = max(5_000, min(timeout_ms, 120_000))

    try:
        raw = _analyze_with_browser(url, wait_until=wait_until, timeout_ms=timeout_ms)
    except Exception as exc:
        log.exception("browser SEO analysis failed")
        return json.dumps(
            {"error": f"Browser analysis failed: {exc}", "url": url},
            ensure_ascii=False,
        )

    page = raw.get("page") or {}
    json_ld_raw = page.get("json_ld") or []
    structured_data_summary = _summarize_json_ld(json_ld_raw if isinstance(json_ld_raw, list) else [])

    payload = {
        "final_url": raw.get("final_url"),
        "http_status": raw.get("http_status"),
        "wait_until": wait_until,
        "document_title": page.get("document_title", ""),
        "html_lang": page.get("html_lang"),
        "meta": page.get("meta"),
        "link_rels": page.get("link_rels"),
        "headings": page.get("headings"),
        "word_count_visible": page.get("word_count_visible"),
        "json_ld_blocks": len(json_ld_raw) if isinstance(json_ld_raw, list) else 0,
        "structured_data_types": structured_data_summary,
        "json_ld": json_ld_raw,
        "detected_issues": _detect_issues(page),
    }

    return json.dumps(payload, ensure_ascii=False)


analyze_page_seo = Capability(
    name="analyze_page_seo",
    description=(
        "Analyze a URL with headless Chromium (Playwright). "
        "Returns DOM after JavaScript: document title, meta tags (incl. og/twitter), "
        "link rel (canonical, alternate/hreflang), H1–H6, visible word count, JSON-LD structured data, "
        "and detected SEO issues. Use for technical SEO and structured data. "
        "For reading article/body text, use fetch_url (also renders with Chromium by default)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL (https://...)"},
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "description": "When navigation is considered done. Default load (reliable). Use networkidle only for SPAs that need a quiet network.",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Navigation timeout in ms (default 45000, max 120000)",
            },
        },
        "required": ["url"],
    },
    handler=_handle_analyze_page_seo,
)
