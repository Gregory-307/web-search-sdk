import types

import pytest

from web_search_sdk.scrapers import duckduckgo_web as ddg
from web_search_sdk.scrapers.base import ScraperContext


@pytest.mark.asyncio
async def test_ddg_logger_tag(monkeypatch):
    events = []

    def _capture(msg: str, **kw):  # type: ignore
        events.append((msg, kw))

    monkeypatch.setattr(ddg.logger, "info", _capture)

    # Dummy AsyncClient class
    class _Resp:
        text = "<html></html>"
        status_code = 200

        def raise_for_status(self):
            pass

    class _DummyClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **_kw):
            return _Resp()

        async def aclose(self):
            pass

    monkeypatch.setattr(ddg, "httpx", types.SimpleNamespace(AsyncClient=_DummyClient))

    ctx = ScraperContext(debug=True)
    await ddg.fetch_serp_html("openai", ctx)

    assert events, "Logger did not emit events"
    # First event is http_get
    tag, data = events[0]
    assert tag == "http_get"
    assert "url" in data
