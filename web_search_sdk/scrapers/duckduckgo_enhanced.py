"""DuckDuckGo HTML search with explicit success/empty/blocked/error status."""

from __future__ import annotations

import urllib.parse as _uparse
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup

from web_search_sdk.models import SearchItem, SearchResponse, SearchStatus
from web_search_sdk.utils.http import fetch_text
from web_search_sdk.utils.logging import get_logger
from web_search_sdk.utils.text import most_common, tokenise

from .base import ScraperContext

logger = get_logger("DDG-Enhanced")

__all__ = ["ddg_search_and_parse", "ddg_search_raw"]

_DDG_SEARCH_URL = "https://html.duckduckgo.com/html/?q={}&kl=us-en"
_BLOCK_MARKERS = (
    "anomaly-modal",
    "are you a robot",
    "captcha",
    "challenge-form",
    "request blocked",
    "unusual traffic",
)


def _unwrap_ddg_url(ddg_url: str) -> str:
    """Return the target URL when DuckDuckGo supplies a redirect wrapper."""

    if "duckduckgo.com/l/" in ddg_url:
        try:
            query = parse_qs(urlparse(ddg_url).query)
            if "uddg" in query:
                return unquote(query["uddg"][0])
        except (TypeError, ValueError):
            pass
    return ddg_url


async def _fetch_html(term: str, ctx: ScraperContext) -> str:
    headers = ctx.headers.copy()
    headers.setdefault(
        "User-Agent",
        ctx.choose_ua() or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    headers.setdefault("Accept-Language", "en-US,en;q=0.9")
    url = _DDG_SEARCH_URL.format(_uparse.quote(term))
    if ctx.debug:
        logger.info("http_get", url=url)
    return await fetch_text(
        url,
        retries=ctx.retries,
        timeout=ctx.timeout,
        proxy=ctx.proxy,
        headers=headers,
        user_agents=ctx.user_agents,
        scraper="duckduckgo-html",
    )


def _extract_publisher(url: str) -> str:
    try:
        domain = urlparse(url).netloc
        return domain.removeprefix("www.").split(".")[0].upper()
    except (AttributeError, ValueError):
        return "UNKNOWN"


def _parse_html(html: str, top_n: int = 10, *, term: str = "unknown") -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[SearchItem] = []
    links: list[str] = []
    legacy_results: list[dict[str, object]] = []
    all_text: list[str] = []

    for rank, result in enumerate(soup.select("div.result"), start=1):
        title_node = result.select_one("a.result__a")
        snippet_node = result.select_one("a.result__snippet, div.result__snippet")
        title = title_node.get_text(" ", strip=True) if title_node else None
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else None
        raw_url = title_node.get("href") if title_node else None
        url = _unwrap_ddg_url(str(raw_url)) if raw_url else None
        text = snippet or title
        if not text:
            continue
        publisher = _extract_publisher(url) if url else None
        item = SearchItem(
            source="duckduckgo",
            title=title,
            text=text,
            url=url,
            publisher=publisher,
            rank=rank,
        )
        items.append(item)
        if url:
            links.append(url)
        legacy_results.append(
            {
                "title": title,
                "snippet": snippet,
                "text": text,
                "url": url,
                "source": publisher,
            }
        )
        all_text.extend(part for part in (title, snippet) if part)
        if len(items) >= top_n:
            break

    words = most_common(tokenise(" ".join(all_text)), top_n)
    lowered = html.lower()
    blocked = not items and any(marker in lowered for marker in _BLOCK_MARKERS)
    response = SearchResponse(
        source="duckduckgo",
        query=term,
        status=(
            SearchStatus.SUCCESS
            if items
            else SearchStatus.BLOCKED
            if blocked
            else SearchStatus.EMPTY
        ),
        items=items,
        top_words=words,
        blocked_reason="provider_challenge" if blocked else None,
    )
    return response.as_dict(
        links=links[:top_n],
        tokens=words,
        results=legacy_results[:top_n],
    )


async def ddg_search_raw(
    term: str,
    ctx: ScraperContext | None = None,
) -> BeautifulSoup:
    """Return the raw DuckDuckGo document for explicit diagnostic use."""

    context = ctx or ScraperContext(use_browser=False)
    html = await _fetch_html(term, context)
    return BeautifulSoup(html or "", "html.parser")


async def ddg_search_and_parse(
    term: str,
    ctx: ScraperContext | None = None,
    top_n: int = 10,
) -> dict[str, object]:
    """Return normalized results and a truthful provider status."""

    context = ctx or ScraperContext(use_browser=False)
    try:
        html = await _fetch_html(term, context)
    except Exception as exc:
        return SearchResponse(
            source="duckduckgo",
            query=term,
            status=SearchStatus.ERROR,
            error=type(exc).__name__,
        ).as_dict(links=[], tokens=[], results=[])
    return _parse_html(html, top_n=top_n, term=term)
