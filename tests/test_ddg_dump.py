import pytest

from web_search_sdk.scrapers import duckduckgo_web as ddg
from web_search_sdk.scrapers.base import ScraperContext


@pytest.mark.asyncio
async def test_ddg_debug_dump(monkeypatch, tmp_path):
    # Prepare dummy fetch returning html
    async def _dummy_fetch(term, ctx):
        return "<html><body>dummy</body></html>"

    monkeypatch.setattr(ddg, "_fetch_html", _dummy_fetch)

    # Patch logger to silence
    monkeypatch.setattr(ddg.logger, "info", lambda *a, **kw: None)

    # Redirect dump dir
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("DEBUG_DUMP", "1")

    ctx = ScraperContext(debug=True)
    await ddg.fetch_serp_html("open ai", ctx)

    expected = tmp_path / "tmp" / "ddg_open_ai.html"
    assert expected.exists(), f"Expected dump file {expected} not found"
    assert expected.read_text() == "<html><body>dummy</body></html>"
