import importlib
from contextlib import asynccontextmanager

import pytest

from web_search_sdk.utils import http as http_utils


@pytest.mark.asyncio
async def test_http_logging_body_len(monkeypatch):
    """When DEBUG_SCRAPERS=1 and DEBUG_TRACE unset, log should include body_len and no preview."""
    # Reload module with env flags so patch applies
    monkeypatch.setenv("DEBUG_SCRAPERS", "1")
    if "web_search_sdk.utils.http_logging" in importlib.sys.modules:
        importlib.reload(importlib.sys.modules["web_search_sdk.utils.http_logging"])
    else:
        importlib.import_module("web_search_sdk.utils.http_logging")

    events = []

    def _capture(_msg: str, **data):  # type: ignore
        events.append((_msg, data))

    # Patch logger used in http_logging
    from web_search_sdk.utils import logging as log_mod

    monkeypatch.setattr(log_mod.get_logger("httpx"), "info", _capture)

    # Dummy client
    @asynccontextmanager
    async def _dummy_client(**_kw):  # type: ignore
        class _Resp:
            status_code = 200
            content = b"hello"
            text = "hello"

            def raise_for_status(self):
                pass

            async def aread(self):  # type: ignore
                return self.content

        class _Cli:
            async def get(self, _url, **_kw):
                return _Resp()

            async def aclose(self):
                pass

        yield _Cli()

    monkeypatch.setattr(http_utils, "get_async_client", _dummy_client)

    await http_utils.fetch_text("http://example.com")

    # Find response event
    resp_events = [d for m, d in events if m == "response"]
    assert resp_events, "No response event captured"
    evt = resp_events[0]
    assert "body_len" in evt and evt["body_len"] == 5
    assert "preview" not in evt, "Preview should not be logged without DEBUG_TRACE"
