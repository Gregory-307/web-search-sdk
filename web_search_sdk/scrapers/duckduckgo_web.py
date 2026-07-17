"""
DuckDuckGo Web Search scraper (async)
------------------------------------
A lightweight HTML-only scraper that fetches the static DuckDuckGo search
results page and extracts the most frequent words and the outbound result
links.  Designed as a drop-in alternative to the Google scraper when
Google blocks or captchas become an issue.

The implementation purposely keeps the dependency footprint identical to
other scrapers in *web_search_sdk* (httpx + BeautifulSoup) and borrows the
same tokenisation helpers so we get consistent output across engines.

DEPRECATED: This module is kept for internal fallback only. Use the enhanced
duckduckgo_enhanced.py module instead.

INTERNAL USE ONLY: Do not import this module in user code.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import urllib.parse as _uparse
import warnings
from collections import Counter
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from web_search_sdk.utils.logging import get_logger

from ..utils.http import _DEFAULT_UA
from .base import ScraperContext, run_scraper

warnings.warn(
    "duckduckgo_web module is deprecated and will be removed in a future version. "
    "Use the enhanced duckduckgo_enhanced module instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = get_logger("DDG")

__all__ = [
    "fetch_serp_html",
    "duckduckgo_top_words",
]

# The HTML endpoint serves a fully rendered, JavaScript-free version of the
# SERP which is perfect for headless scraping.  We request *us-en* locale to
# keep results stable.
_SEARCH_URL = "https://html.duckduckgo.com/html/?q={}&kl=us-en"

_DEFAULT_TOP_N = 20
_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")

# Re-use global stopwords list shared by google_web.py to stay DRY.
_stopwords_path = Path(__file__).resolve().parent.parent / "resources" / "stopwords.txt"
try:
    _STOPWORDS: set[str] = {
        line.strip().lower()
        for line in _stopwords_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
except FileNotFoundError:
    _STOPWORDS = set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Return simple word tokens (ASCII letters, length ≥2)."""
    return _TOKEN_RE.findall(text.lower())


def _tokenise_and_bigrams(text: str) -> list[str]:
    toks = _tokenise(text)
    bigrams = [f"{a} {b}" for a, b in zip(toks, toks[1:], strict=False)]
    return toks + bigrams


async def _fetch_html(term: str, ctx: ScraperContext) -> str:
    headers = ctx.headers.copy()
    ua = ctx.choose_ua() or random.choice(_DEFAULT_UA)
    headers.setdefault("User-Agent", ua)
    headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    headers.setdefault(
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    )

    url = _SEARCH_URL.format(_uparse.quote(term))
    if ctx.debug:
        logger.info("http_get", url=url)

    for attempt in range(ctx.retries + 1):
        try:
            client_kwargs = {"timeout": ctx.timeout}
            if ctx.proxy:
                client_kwargs["proxy"] = ctx.proxy

            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                resp.raise_for_status()
                return resp.text
        except Exception as exc:
            if attempt >= ctx.retries:
                raise exc
            await asyncio.sleep(0.3 * (attempt + 1))

    return ""  # Should not reach here


def _parse_html(html: str, top_n: int = _DEFAULT_TOP_N) -> list[str]:
    """Extract most frequent words/bigrams from a DDG SERP HTML."""

    soup = BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------------
    # Extract result blocks – DDG HTML endpoint structure
    #   <a class="result__a">Title</a>
    #   <a class="result__snippet">Snippet</a> OR <div class="result__snippet">
    #   Optional  <a class="result__url" href="…"> (hidden)
    # The parser now collects both *text* (for tokenisation) and *links* so
    # callers that need outbound URLs can post-process.
    # ------------------------------------------------------------------

    titles_nodes = soup.select("a.result__a")
    snippets_nodes = soup.select("a.result__snippet, div.result__snippet")
    titles = [n.get_text(" ").strip() for n in titles_nodes]
    snippets = [n.get_text(" ").strip() for n in snippets_nodes]

    # When DDG returns zero titles (rare but possible for empty result set)
    # we fall back to any <h2> or <h3> that might denote "result" card.
    if not titles:
        titles = [h.get_text(" ").strip() for h in soup.find_all(["h2", "h3"])]

    combined_text = " ".join(titles + snippets)

    # ------------------------------------------------------------------
    # Tokenisation – reuse shared helpers then drop stop-words and sort by
    # frequency.  We also deduplicate while preserving frequency ranking.
    # ------------------------------------------------------------------

    tokens = [t for t in _tokenise_and_bigrams(combined_text) if t not in _STOPWORDS]

    counter = Counter(tokens)

    # Preserve order by frequency but remove duplicates via dict keys.
    top_tokens: list[str] = []
    for tok, _freq in counter.most_common():
        if tok not in top_tokens:
            top_tokens.append(tok)
        if len(top_tokens) == top_n:
            break

    return top_tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_serp_html(term: str, ctx: ScraperContext | None = None) -> str:
    """Return raw DuckDuckGo SERP HTML.

    For DDG we always use the HTTP path as the html.duckduckgo.com endpoint
    is lightweight and rarely blocked.  Browser rendering offers no benefit
    here and is therefore skipped – if *ctx.use_browser* is True we simply
    proceed with the same HTTP request (KISS & YAGNI).
    """

    ctx = ctx or ScraperContext()
    html = await _fetch_html(term, ctx)

    # Optional debug dump ---------------------------------------------------
    if os.getenv("DEBUG_DUMP") in {"1", "true", "True"} and html:
        safe_term = _uparse.quote(term.replace(" ", "_"), safe="")
        dump_dir = Path("tmp")
        dump_dir.mkdir(exist_ok=True)
        file_path = dump_dir / f"ddg_{safe_term}.html"
        try:
            file_path.write_text(html, encoding="utf-8")
            if ctx.debug:
                logger.info("html_dump", path=str(file_path))
        except Exception as exc:
            if ctx.debug:
                logger.info("html_dump_error", error=str(exc))

    return html


async def duckduckgo_top_words(
    term: str,
    ctx: ScraperContext = None,
    top_n: int = _DEFAULT_TOP_N,
) -> list[str]:
    """Return most common words from DuckDuckGo search results for *term*."""
    if ctx is None:
        ctx = ScraperContext(use_browser=False)  # HTTP context works fine for DuckDuckGo

    # Validate context
    if ctx.use_browser:
        print(
            "💡 Tip: duckduckgo_top_words works fine with HTTP context (faster). Browser context is optional."
        )

    def _parse_wrapper(html: str, t: str, c: ScraperContext):
        # _parse_html expects only (html, top_n)
        return _parse_html(html, top_n)

    return await run_scraper(term, _fetch_html, _parse_wrapper, ctx)
