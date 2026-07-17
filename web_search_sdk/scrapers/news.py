"""Google News RSS acquisition with truthful structured output."""

from __future__ import annotations

import re
import urllib.parse as _uparse
from collections import Counter
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path

from bs4 import BeautifulSoup

from web_search_sdk.models import SearchItem, SearchResponse, SearchStatus
from web_search_sdk.utils.http import fetch_text
from web_search_sdk.utils.logging import get_logger

from .base import ScraperContext, run_in_thread, run_scraper

logger = get_logger("NEWS")

__all__ = ["google_news_top_words", "google_news", "google_news_raw"]

RSS_URL = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
DEFAULT_TOP_N = 20

_stopwords_path = Path(__file__).resolve().parent.parent / "resources" / "stopwords.txt"
try:
    _STOPWORDS: set[str] = {
        line.strip().lower()
        for line in _stopwords_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
except FileNotFoundError:
    _STOPWORDS = set()


async def _fetch_rss(term: str, ctx: ScraperContext) -> str:
    headers = ctx.headers.copy()
    user_agent = ctx.choose_ua()
    if user_agent:
        headers["User-Agent"] = user_agent
    return await fetch_text(
        RSS_URL.format(_uparse.quote(term)),
        retries=ctx.retries,
        timeout=ctx.timeout,
        proxy=ctx.proxy,
        headers=headers,
        user_agents=ctx.user_agents,
        scraper="google-news-rss",
    )


def _tokenise(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]{2,}", text.lower())


def _top_words(texts: list[str], top_n: int) -> list[str]:
    tokens = _tokenise(" ".join(texts))
    filtered = [token for token in tokens if token not in _STOPWORDS] or tokens
    return [token for token, _ in Counter(filtered).most_common(top_n)]


def _parse_rss(xml: str, top_n: int = DEFAULT_TOP_N) -> list[str]:
    soup = BeautifulSoup(xml, "xml")
    return _top_words(
        [item.title.get_text() for item in soup.find_all("item") if item.title],
        top_n,
    )


def _parse_timestamp(value: str | None):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_rss_structured(
    xml: str,
    *,
    term: str,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, object]:
    """Parse RSS into canonical items while retaining truthful legacy arrays."""

    soup = BeautifulSoup(xml, "xml")
    items: list[SearchItem] = []
    headlines: list[str] = []
    summaries: list[str] = []
    sources: list[str] = []

    for rank, node in enumerate(soup.find_all("item"), start=1):
        title = node.title.get_text(" ", strip=True) if node.title else ""
        raw_description = node.description.get_text(" ", strip=True) if node.description else ""
        description = BeautifulSoup(raw_description, "html.parser").get_text(" ", strip=True)
        publisher = node.source.get_text(" ", strip=True) if node.source else "Unknown"
        link = node.link.get_text(" ", strip=True) if node.link else None
        published = _parse_timestamp(
            node.pubDate.get_text(" ", strip=True) if node.pubDate else None
        )
        text = description or title
        if not text:
            continue
        items.append(
            SearchItem(
                source="google_news",
                title=title or None,
                text=text,
                url=link or None,
                published_at=published,
                publisher=publisher,
                rank=rank,
            )
        )
        headlines.append(title)
        summaries.append(description)
        sources.append(publisher)
        if len(items) >= top_n:
            break

    response = SearchResponse(
        source="google_news",
        query=term,
        status=SearchStatus.SUCCESS if items else SearchStatus.EMPTY,
        items=items,
        top_words=_top_words([*headlines, *summaries], top_n),
    )
    return response.as_dict(
        headlines=headlines,
        summaries=summaries,
        sources=sources,
    )


async def google_news_raw(term: str, ctx: ScraperContext | None = None) -> str:
    """Return the raw Google News RSS response."""

    return await _fetch_rss(term, ctx or ScraperContext(use_browser=False))


async def google_news(
    term: str,
    ctx: ScraperContext | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, object]:
    """Return structured Google News items with explicit provider status."""

    context = ctx or ScraperContext(use_browser=False)

    def _parse_wrapper(xml: str, _term: str, _ctx: ScraperContext) -> dict[str, object]:
        return _parse_rss_structured(xml, term=term, top_n=top_n)

    try:
        result = await run_scraper(term, _fetch_rss, _parse_wrapper, context)
        if context.debug:
            logger.info("rss_structured", term=term, items=len(result.get("items", [])))
        return result
    except Exception as exc:
        if context.debug:
            logger.info("provider_error", term=term, error_type=type(exc).__name__)
        return SearchResponse(
            source="google_news",
            query=term,
            status=SearchStatus.ERROR,
            error=type(exc).__name__,
        ).as_dict(headlines=[], summaries=[], sources=[])


async def google_news_top_words(
    term: str,
    ctx: ScraperContext | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> list[str]:
    """Return the legacy token list, preferring its historical HTML parser."""

    context = ctx or ScraperContext(use_browser=False)
    try:
        from .news_legacy import top_words_sync

        words = await run_in_thread(
            top_words_sync,
            term,
            top_n=top_n,
            headers=context.headers,
            timeout=context.timeout,
        )
        if words:
            return words
    except Exception:
        pass

    def _parse_wrapper(xml: str, _term: str, _ctx: ScraperContext) -> list[str]:
        return _parse_rss(xml, top_n)

    try:
        return await run_scraper(term, _fetch_rss, _parse_wrapper, context)
    except Exception:
        return []
