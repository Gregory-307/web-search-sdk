from contextlib import asynccontextmanager

import pytest

from web_search_sdk.utils import http as http_utils


@pytest.mark.asyncio
async def test_fetch_text_emits_telemetry(monkeypatch):
    """Ensure fetch_text emits telemetry JSON when LOG_SCRAPERS is set."""
    events: list[dict] = []

    # Patch logger.info to capture events instead of printing
    def _capture(_msg: str, **data):  # type: ignore
        events.append(data)

    monkeypatch.setattr(http_utils.logger, "info", _capture)

    # Dummy httpx client to avoid real network
    @asynccontextmanager
    async def _dummy_client(**_kw):  # type: ignore
        class _Resp:  # minimal response stub
            status_code = 200
            content = b"ok"
            text = "ok"

            def raise_for_status(self):
                return None

        class _Cli:
            async def get(self, _url, **_kw):
                return _Resp()

            async def aclose(self):
                return None

        yield _Cli()

    monkeypatch.setattr(http_utils, "get_async_client", _dummy_client)

    # Ensure env flag is set
    monkeypatch.setenv("LOG_SCRAPERS", "1")

    # Run fetch_text
    txt = await http_utils.fetch_text("http://example.com")
    assert txt == "ok"

    # Validate telemetry captured
    assert events, "No telemetry events captured"
    evt = events[0]
    for key in ("url", "status", "elapsed_ms", "content_len", "scraper"):
        assert key in evt
    assert evt["url"] == "http://example.com"
    assert evt["status"] == 200
    assert evt["content_len"] == len("ok")
