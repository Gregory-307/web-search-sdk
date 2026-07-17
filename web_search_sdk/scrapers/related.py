"""Scraper for https://relatedwords.org – returns a list of related words.

Functional style – expose a single high-level coroutine `related_words` and
stateless helper functions.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from .base import ScraperContext, run_in_thread, run_scraper

# Optional Selenium fallback
with suppress(ImportError):
    from bs4 import BeautifulSoup  # ensure available for fallback
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

__all__ = ["related_words"]

# prefer JSON API
HTML_URL = "https://relatedwords.org/relatedto/{}"
API_URL = "https://relatedwords.org/api/related?term={}&max=50"


# ---------------------------------------------------------------------------
# Low-level fetch & parse helpers
# ---------------------------------------------------------------------------


# first try JSON api
async def _fetch_json_or_html(term: str, ctx: ScraperContext) -> str | list[str]:
    """Download the HTML for a single seed term."""
    json_url = API_URL.format(term.replace(" ", "%20"))

    headers = ctx.headers.copy()
    ua = ctx.choose_ua()
    if ua:
        headers["User-Agent"] = ua

    # attempt JSON API first
    try:
        async with httpx.AsyncClient(timeout=ctx.timeout, proxy=ctx.proxy) as client:
            resp = await client.get(json_url, headers=headers)
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith(
                "application/json"
            ):
                data = resp.json()
                return [item["word"] for item in data if "word" in item]
    except Exception:
        pass

    # fallback to HTML scraping
    url = HTML_URL.format(term.replace(" ", "%20"))

    for attempt in range(ctx.retries + 1):
        try:
            async with httpx.AsyncClient(timeout=ctx.timeout, proxy=ctx.proxy) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            if attempt >= ctx.retries:
                raise exc
            await asyncio.sleep(0.5 * (attempt + 1))


def _parse_html(raw: str, term: str, ctx: ScraperContext) -> list[str]:
    """Extract related words from the HTML document."""
    # raw may already be list
    if isinstance(raw, list):
        return raw

    soup = BeautifulSoup(raw, "html.parser")
    items = soup.select("a.item")
    # some entries contain counts like "word (42)" – strip parens
    words: list[str] = [item.text.split(" (")[0].strip() for item in items if item.text]
    return words


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def related_words(term: str, ctx: ScraperContext | None = None) -> list[str]:
    """Return a list of related words for *term* (empty list if not found)."""
    if ctx is None:
        ctx = ScraperContext()

    # First: legacy HTML scrape (blocking)
    try:
        from .related_legacy import related_words_sync

        words = await run_in_thread(
            related_words_sync, term, headers=ctx.headers, timeout=ctx.timeout
        )
        if ctx.debug:
            print(f"[RelatedWords-Legacy] {term} -> {len(words)} words via HTML")
        if words:
            return words
    except Exception:
        pass

    # Second: JSON or raw HTML via httpx
    try:
        words = await run_scraper(term, _fetch_json_or_html, _parse_html, ctx)
        if ctx.debug:
            print(f"[RelatedWords-API] {term} -> {len(words)} words via JSON/HTML api")
        if words:
            return words
        # additional fallback to Datamuse API if RelatedWords is empty
        try:
            async with httpx.AsyncClient(timeout=ctx.timeout, proxy=ctx.proxy) as client:
                dm_url = f"https://api.datamuse.com/words?rel_trg={quote(term)}&max=50"
                resp = await client.get(dm_url)
                if resp.status_code == 200:
                    data = resp.json()
                    words = [item["word"] for item in data if "word" in item]
                    if words:
                        return words
        except Exception:
            pass

    except Exception:
        pass

    # Third: optional Selenium fallback – only if Selenium is available
    if ctx.use_browser and "webdriver" in globals() and "Options" in globals():
        print("[RelatedWords] FALLBACK to Selenium – performing slow browser fetch…")
        try:
            opts = Options()
            opts.add_argument("--headless")
            driver = webdriver.Firefox(options=opts)
            url = HTML_URL.format(term.replace(" ", "%20"))
            driver.get(url)
            html = driver.page_source
            driver.quit()
            soup = BeautifulSoup(html, "html.parser")
            items = soup.select("a.item")
            words = [i.text.split(" (", 1)[0].strip() for i in items if i.text]
            if ctx.debug:
                print(f"[RelatedWords-Selenium] {term} -> {len(words)} words via browser")
            return words
        except Exception as e:
            print(f"[RelatedWords] Selenium fallback failed: {e}")
            return []

    if ctx.debug:
        print(f"[RelatedWords] {term} – no data found")
    return []
