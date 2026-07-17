import asyncio

from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.scrapers.google_web import fetch_serp_html


def test_no_http_when_browser(monkeypatch):
    """Ensure _fetch_html is never invoked when ctx.use_browser is True."""

    # Patch _fetch_html to raise if called
    def _boom(*args, **kwargs):
        raise RuntimeError("HTTP fetch should not be called when browser active")

    monkeypatch.setattr("web_search_sdk.scrapers.google_web._fetch_html", _boom, raising=True)

    # Patch browser fetch to return dummy html
    async def _fake_browser(term, url_fn, ctx):
        return "<html>ok</html>"

    monkeypatch.setattr(
        "web_search_sdk.scrapers.google_web._browser_fetch_html", _fake_browser, raising=True
    )

    ctx = ScraperContext(use_browser=True, browser_type="playwright_stealth")
    html = asyncio.run(fetch_serp_html("btc rally", ctx))
    assert "ok" in html
