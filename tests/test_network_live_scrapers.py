"""Live smoke test hitting the real internet once (web_search_sdk subset).

Checks RelatedWords, Wikipedia and Google News scrapers only.
"""

import socket

import pytest

from web_search_sdk.scrapers import (
    google_news_top_words as news_scraper,
)
from web_search_sdk.scrapers import (
    related_words as related_scraper,
)
from web_search_sdk.scrapers import (
    wikipedia_top_words as wiki_scraper,
)
from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.utils.http import _DEFAULT_UA

from .conftest import show

pytestmark = [pytest.mark.asyncio, pytest.mark.live]

TERMS = ["python", "technology", "dog", "music"]
WIKI_ARTICLES = [
    "Python_(programming_language)",
    "Technology",
    "Dog",
    "Music",
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CTX = ScraperContext(headers=DEFAULT_HEADERS, user_agents=_DEFAULT_UA, debug=False)


async def test_live_scrapers_subset():
    # Skip if offline
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
    except OSError:
        pytest.skip("No network connectivity – skipping live scraper test")

    reasons = []

    # RelatedWords
    try:
        rel_found = False
        for term in TERMS:
            if await related_scraper(term, ctx=CTX):
                rel_found = True
                break
    except Exception as e:
        reasons.append(f"RelatedWords error: {e}")
        raise

    # Wikipedia
    try:
        wiki_found = False
        for art in WIKI_ARTICLES:
            if await wiki_scraper(art, top_n=20, ctx=CTX):
                wiki_found = True
                break
    except Exception as e:
        reasons.append(f"Wikipedia error: {e}")
        raise

    # Google News
    try:
        news_found = False
        for term in TERMS:
            if await news_scraper(term, top_n=10, ctx=CTX):
                news_found = True
                break
    except Exception as e:
        reasons.append(f"Google News error: {e}")
        raise

    overall = all([rel_found, wiki_found, news_found])
    summary = (
        f"RelatedWords : {rel_found}\nWikipedia     : {wiki_found}\nGoogle News   : {news_found}"
    )
    status = "PASS" if overall else "FAIL"
    show("LIVE", "scrapers subset", "Completed", summary, status=status)

    if not overall:
        pytest.fail("; ".join(reasons) if reasons else "Some sources returned empty data")
