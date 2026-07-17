"""Search orchestration with explicit final provider status."""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from web_search_sdk.models import SearchItem, SearchResponse, SearchStatus

from .base import ScraperContext


async def _fetch_serp_html(term: str, ctx: ScraperContext) -> str:
    """Fetch fallback SERP HTML using legacy DDG, then Google."""

    from . import duckduckgo_web as ddg

    html = await ddg.fetch_serp_html(term, ctx)
    if html:
        return html

    from . import google_web as google

    return await google.fetch_serp_html(term, ctx)


async def search_and_parse_basic(
    term: str,
    ctx: ScraperContext | None = None,
    top_n: int = 10,
    return_links: bool = True,
) -> dict[str, object]:
    """Parse the legacy fallback SERP into the normalized response shape."""

    context = ctx or ScraperContext(use_browser=False)
    raw_html = await _fetch_serp_html(term, context)
    soup = BeautifulSoup(raw_html, "html.parser")
    tokens = soup.get_text(" ", strip=True).split()[:top_n]
    links: list[str] = []
    items: list[SearchItem] = []
    if return_links:
        for anchor in soup.find_all("a", href=True):
            url = str(anchor["href"])
            if urlparse(url).scheme not in {"http", "https"}:
                continue
            title = anchor.get_text(" ", strip=True) or None
            links.append(url)
            items.append(
                SearchItem(
                    source="serp_fallback",
                    title=title,
                    text=title or url,
                    url=url,
                    publisher=urlparse(url).netloc or None,
                    rank=len(items) + 1,
                )
            )
            if len(items) >= top_n:
                break
    response = SearchResponse(
        source="serp_fallback",
        query=term,
        status=SearchStatus.SUCCESS if items else SearchStatus.EMPTY,
        items=items,
        top_words=tokens,
    )
    return response.as_dict(links=links, tokens=tokens, results=[])


async def search_and_parse(
    term: str,
    ctx: ScraperContext | None = None,
    top_n: int = 10,
    return_links: bool = True,
) -> dict[str, object]:
    """Use enhanced DDG first and retain explicit status through fallback."""

    from .duckduckgo_enhanced import ddg_search_and_parse

    context = ctx or ScraperContext(use_browser=False)
    try:
        enhanced = await ddg_search_and_parse(term, context, top_n)
    except Exception as exc:
        enhanced = SearchResponse(
            source="duckduckgo",
            query=term,
            status=SearchStatus.ERROR,
            error=type(exc).__name__,
        ).as_dict(links=[], tokens=[], results=[])
    if enhanced["status"] in {SearchStatus.SUCCESS, SearchStatus.BLOCKED}:
        return enhanced

    try:
        fallback = await search_and_parse_basic(term, context, top_n, return_links)
    except Exception:
        return enhanced
    if fallback.get("status") == SearchStatus.SUCCESS or fallback.get("links"):
        return fallback
    return enhanced


__all__ = ["search_and_parse", "search_and_parse_basic"]
