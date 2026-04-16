"""Accessibility audits with Deque axe-core (WCAG 2.2) via Playwright.

Loads the official axe-core browser bundle, then runs axe.run() in the page context.

Axe is fetched in the Python process (or read from a vendored file) and injected with
``add_script_tag(content=...)`` so strict page CSP (e.g. script-src without third-party
hosts) does not block it — unlike loading the same CDN URL in the browser.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from typing import Any

from orqestra.capabilities.browser_core import (
    DEFAULT_TIMEOUT_MS,
    DEFAULT_WAIT_UNTIL,
    playwright_available,
    playwright_page,
)
from orqestra.core.capabilities import Capability

log = logging.getLogger(__name__)

# Pinned npm release — https://www.npmjs.com/package/axe-core
AXE_CORE_VERSION = "4.10.3"
AXE_MIN_JS_URL = f"https://cdn.jsdelivr.net/npm/axe-core@{AXE_CORE_VERSION}/axe.min.js"

# Optional: place axe.min.js here for air-gapped runs (same version as AXE_CORE_VERSION).
_VENDOR_AXE_PATH = Path(__file__).resolve().parent / "vendor" / f"axe-core-{AXE_CORE_VERSION}.min.js"

_AXE_JS_CACHE: str | None = None

# WCAG 2.2 Level AA (includes 2.0 / 2.1 AA rules carried forward)
WCAG_22_AA_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]

_MAX_VIOLATIONS_IN_RESPONSE = 40


def _load_axe_core_js() -> str:
    """Return axe.min.js source. Cached in-process; prefers vendored file, else HTTPS fetch."""
    global _AXE_JS_CACHE
    if _AXE_JS_CACHE is not None:
        return _AXE_JS_CACHE
    if _VENDOR_AXE_PATH.is_file():
        _AXE_JS_CACHE = _VENDOR_AXE_PATH.read_text(encoding="utf-8")
        return _AXE_JS_CACHE
    req = urllib.request.Request(
        AXE_MIN_JS_URL,
        headers={"User-Agent": "orqestra/axe-wcag-scan"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        _AXE_JS_CACHE = resp.read().decode("utf-8")
    return _AXE_JS_CACHE


def _summarize_axe_result(raw: dict[str, Any]) -> dict[str, Any]:
    violations = raw.get("violations") or []
    incomplete = raw.get("incomplete") or []

    slim_violations: list[dict[str, Any]] = []
    for v in violations[:_MAX_VIOLATIONS_IN_RESPONSE]:
        nodes = v.get("nodes") or []
        slim_violations.append(
            {
                "id": v.get("id"),
                "impact": v.get("impact"),
                "help": v.get("help"),
                "description": v.get("description"),
                "helpUrl": v.get("helpUrl"),
                "tags": [t for t in (v.get("tags") or []) if str(t).startswith("wcag")],
                "nodes_count": len(nodes),
                "sample_targets": [
                    n.get("target") for n in nodes[:5] if isinstance(n, dict)
                ],
            }
        )

    slim_incomplete: list[dict[str, Any]] = []
    for item in incomplete[:15]:
        nodes = item.get("nodes") or []
        slim_incomplete.append(
            {
                "id": item.get("id"),
                "impact": item.get("impact"),
                "help": item.get("help"),
                "helpUrl": item.get("helpUrl"),
                "nodes_count": len(nodes),
            }
        )

    return {
        "tool": "axe-core",
        "axe_core_version": AXE_CORE_VERSION,
        "standard": "WCAG 2.2 Level AA (axe tag filter: wcag2a, wcag2aa, wcag21aa, wcag22aa)",
        "passes": len(raw.get("passes") or []),
        "violations_count": len(violations),
        "incomplete_count": len(incomplete),
        "violations": slim_violations,
        "incomplete_sample": slim_incomplete,
        "truncated_violations": len(violations) > _MAX_VIOLATIONS_IN_RESPONSE,
    }


def _handle_axe_wcag_scan(args: dict) -> str:
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
        axe_js = _load_axe_core_js()
    except OSError as exc:
        return json.dumps(
            {
                "error": (
                    f"Could not load axe-core ({exc}). "
                    f"Ensure outbound HTTPS to jsDelivr or place the bundle at {_VENDOR_AXE_PATH}"
                ),
                "url": url,
                "axe_source": AXE_MIN_JS_URL,
            },
            ensure_ascii=False,
        )

    try:
        with playwright_page(url, wait_until=wait_until, timeout_ms=timeout_ms) as (page, response):
            final_url = page.url
            http_status = response.status if response else None

            # Inline injection avoids page CSP blocking third-party script URLs.
            page.add_script_tag(content=axe_js)

            tags_js = json.dumps(WCAG_22_AA_TAGS)
            raw_result = page.evaluate(
                f"""
                async () => {{
                    if (typeof axe === "undefined" || typeof axe.run !== "function") {{
                        return {{ __error: "axe-core did not load in page context" }};
                    }}
                    return await axe.run(document, {{
                        runOnly: {{
                            type: "tag",
                            values: {tags_js}
                        }}
                    }});
                }}
                """
            )
    except Exception as exc:
        log.exception("axe WCAG scan failed")
        return json.dumps(
            {"error": f"Scan failed: {exc}", "url": url},
            ensure_ascii=False,
        )

    if isinstance(raw_result, dict) and raw_result.get("__error"):
        return json.dumps(
            {"error": raw_result["__error"], "url": url, "axe_source": AXE_MIN_JS_URL},
            ensure_ascii=False,
        )

    if not isinstance(raw_result, dict):
        return json.dumps(
            {"error": "Unexpected axe response", "url": url},
            ensure_ascii=False,
        )

    payload = {
        "url_requested": url,
        "final_url": final_url,
        "http_status": http_status,
        "summary": _summarize_axe_result(raw_result),
    }

    if args.get("include_raw") is True:
        payload["raw"] = raw_result

    return json.dumps(payload, ensure_ascii=False)


axe_wcag_scan = Capability(
    name="axe_wcag_scan",
    description=(
        "Run an accessibility audit with Deque axe-core in headless Chromium (Playwright). "
        "Uses WCAG 2.2 Level AA rule tags (wcag2a, wcag2aa, wcag21aa, wcag22aa). "
        "Returns violations and incomplete items with impact, selectors, and deque help URLs. "
        "Requires Playwright. axe-core is loaded in-process (HTTPS to jsDelivr or a vendored file under "
        "capabilities/vendor/) so page Content-Security-Policy does not block it."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full page URL to test (https://...)"},
            "wait_until": {
                "type": "string",
                "enum": ["load", "domcontentloaded", "networkidle", "commit"],
                "description": "Navigation wait (default load).",
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Navigation timeout in ms (default 45000)",
            },
            "include_raw": {
                "type": "boolean",
                "description": "If true, include full axe JSON (large). Default false.",
            },
        },
        "required": ["url"],
    },
    handler=_handle_axe_wcag_scan,
)
