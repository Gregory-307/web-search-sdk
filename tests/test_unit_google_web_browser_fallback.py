"""Unit test: browser fallback path in web_search_sdk.google_web_top_words.

The HTTP fetch is monkey-patched to return an empty string so the scraper
must call the browser helper.  We monkey-patch that helper to return a
static HTML snippet, ensuring no actual browser session is launched.
"""

import pytest

from web_search_sdk import browser as br
from web_search_sdk.scrapers import google_web as gw
from web_search_sdk.scrapers import google_web_top_words
from web_search_sdk.scrapers.base import ScraperContext

from .conftest import show

HTML_SNIPPET = """
<html><body>
  <div class='yuRUbf'><a><h3>AI overtakes everything</h3></a></div>
  <div class='IsZvec'>Historic milestone reached…</div>
</body></html>
"""

pytestmark = pytest.mark.asyncio


async def test_browser_fallback_dm(monkeypatch):
    """Ensure fallback path yields tokens when HTTP fetch returns empty."""

    async def fake_fetch_http(term, ctx):
        return ""  # simulate JS-only SERP

    async def fake_browser_async(term, url_fn, ctx):  # noqa: D401
        return HTML_SNIPPET

    monkeypatch.setattr(gw, "_fetch_html", fake_fetch_http)
    monkeypatch.setattr(br, "fetch_html", fake_browser_async)
    monkeypatch.setattr(br, "_SEL_AVAILABLE", True)
    monkeypatch.setattr(gw, "_SEL_AVAILABLE", True)
    monkeypatch.setattr(gw, "_browser_fetch_html", fake_browser_async)

    ctx = ScraperContext(use_browser=True, debug=False)
    tokens = await google_web_top_words("openai", ctx=ctx, top_n=5)

    assert tokens, "Browser fallback should return tokens"
    assert "ai" in tokens[0].lower()

    show("UNIT", "google_web_browser_fallback_dm", "Input  : openai", f"Output : {tokens}")
