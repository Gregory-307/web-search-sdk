import asyncio

from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.scrapers.google_web import fetch_serp_html


def test_fetch_serp_html_selenium_first(monkeypatch):
    """Ensure Selenium fast-path is taken when requested."""

    async def fake_browser(term, url_fn, ctx):
        # Sanity-check the constructed URL contains encoded term
        assert "btc%20rally" in url_fn(term)
        return "<html><title>stub</title></html>"

    monkeypatch.setattr(
        "web_search_sdk.scrapers.google_web._browser_fetch_html", fake_browser, raising=True
    )

    ctx = ScraperContext(use_browser=True, browser_type="selenium", debug=False)

    html = asyncio.run(fetch_serp_html("btc rally", ctx))
    assert "<title>stub</title>" in html
