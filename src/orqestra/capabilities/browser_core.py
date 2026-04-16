"""Shared Playwright/Chromium helpers for rendering pages before scraping or SEO.

All URL fetching that needs the real DOM (JS, SPAs) should go through this module.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 45_000
# "load" finishes when the load event fires. "networkidle" often never completes on real sites
# (analytics, ads, websockets) and causes timeouts; use wait_until=networkidle only when needed for SPAs.
DEFAULT_WAIT_UNTIL = "load"

# Real browser UA — sites often serve minimal HTML to generic bots
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


@contextmanager
def playwright_page(
    url: str,
    *,
    wait_until: str = DEFAULT_WAIT_UNTIL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> Generator[Any, None, None]:
    """Navigate to URL and yield the Playwright Page (Chromium, headless)."""
    from playwright.sync_api import sync_playwright

    if wait_until not in ("load", "domcontentloaded", "networkidle", "commit"):
        wait_until = DEFAULT_WAIT_UNTIL
    timeout_ms = max(5_000, min(int(timeout_ms), 120_000))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        try:
            context = browser.new_context(
                locale="de-DE",
                user_agent=_USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            yield page, response
        finally:
            browser.close()


def fetch_rendered_html(
    url: str,
    *,
    wait_until: str = DEFAULT_WAIT_UNTIL,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> dict[str, Any]:
    """Load URL in Chromium and return final HTML after JavaScript execution."""
    try:
        with playwright_page(url, wait_until=wait_until, timeout_ms=timeout_ms) as (page, response):
            html = page.content()
            return {
                "ok": True,
                "html": html,
                "final_url": page.url,
                "http_status": response.status if response else None,
            }
    except Exception as exc:
        log.warning("fetch_rendered_html failed: %s", exc)
        return {"ok": False, "error": str(exc)}
