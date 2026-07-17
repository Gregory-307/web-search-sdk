import pytest

from web_search_sdk.scrapers import paywall as pw
from web_search_sdk.scrapers.base import ScraperContext

HTML_EXAMPLE = """
<html><body><article><p>Example headline</p><p>Full article body here.</p></article></body></html>
"""


@pytest.mark.asyncio
async def test_paywall_fetch(monkeypatch):
    async def dummy_quick(url, ctx):
        return HTML_EXAMPLE

    async def dummy_browser(url, ctx):
        return HTML_EXAMPLE

    monkeypatch.setattr(pw, "_quick_http_get", dummy_quick)
    monkeypatch.setattr(pw, "_fetch_via_browser", dummy_browser)

    ctx = ScraperContext(use_browser=False)
    text = await pw.fetch_bloomberg("http://example.com/article", ctx)
    assert "Example headline" in text and "Full article body" in text
