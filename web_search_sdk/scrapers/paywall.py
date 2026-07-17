"""Paywalled source helpers (Bloomberg, CNBC).

These helpers use the generic browser.fetch_html() fallback when `ctx.use_browser`
 is True.  If a full browser render is not requested, they attempt a quick
 `httpx` GET first to keep things lightweight (KISS).  The parsed article text
 is returned as a raw string so callers can post-process (tokenise, sentiment, …).

DEPRECATED: This module is kept for backward compatibility only. Use the generic
article_extractor.py module instead.

INTERNAL USE ONLY: Do not import this module in user code.
"""

from __future__ import annotations

import warnings

import httpx
from bs4 import BeautifulSoup

from web_search_sdk import browser as br
from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.utils.logging import get_logger

warnings.warn(
    "paywall module is deprecated and will be removed in a future version. "
    "Use the generic article_extractor module instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = get_logger("CNBC")

__all__ = [
    "fetch_bloomberg",
    "fetch_cnbc",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_article(html: str) -> str:
    """Return visible article text (fallback to full body text)."""
    soup = BeautifulSoup(html, "html.parser")
    art = soup.find("article")
    text = art.get_text(" ", strip=True) if art else soup.get_text(" ", strip=True)
    return text


async def _quick_http_get(url: str, ctx: ScraperContext) -> str:
    try:
        async with httpx.AsyncClient(timeout=ctx.timeout, proxy=ctx.proxy) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return ""


async def _fetch_via_browser(url: str, ctx: ScraperContext) -> str:
    html = await br.fetch_html("_article", lambda _t: url, ctx)
    return html or ""


async def _fetch_and_parse(url: str, ctx: ScraperContext) -> str:
    # 1) Quick HTTP attempt
    raw = await _quick_http_get(url, ctx)
    txt = _extract_article(raw)
    if len(txt) > 200:  # Heuristic: good article length
        if ctx.debug:
            logger.info("quick_http", url=url, chars=len(txt))
        return txt

    # 2) Browser fallback if enabled
    if ctx.use_browser:
        raw = await _fetch_via_browser(url, ctx)
        txt = _extract_article(raw)
        if ctx.debug:
            logger.info("browser_fallback", url=url, chars=len(txt))
    return txt


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


async def fetch_bloomberg(url: str, ctx: ScraperContext | None = None) -> str:
    """Return article text from a Bloomberg URL."""
    ctx = ctx or ScraperContext()
    return await _fetch_and_parse(url, ctx)


async def fetch_cnbc(url: str, ctx: ScraperContext | None = None) -> str:
    """Return article text from a CNBC URL."""
    ctx = ctx or ScraperContext()
    return await _fetch_and_parse(url, ctx)
