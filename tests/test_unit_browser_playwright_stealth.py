from web_search_sdk.browser import fetch_html
from web_search_sdk.scrapers.base import ScraperContext


def test_playwright_stealth_unavailable(monkeypatch):
    """When Playwright is missing and browser_type is stealth, fetch_html should gracefully return ''."""

    monkeypatch.setattr("web_search_sdk.browser._PW_AVAILABLE", False, raising=False)
    ctx = ScraperContext(use_browser=True, browser_type="playwright_stealth")

    import asyncio

    html = asyncio.run(fetch_html("btc rally", lambda t: "https://example.com", ctx))
    assert html == ""
