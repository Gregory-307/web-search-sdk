"""
This test fakes an HTTP GET and expects 'ok'.
It is identical to the version in migration_package but imports from web_search_sdk.
"""

from contextlib import asynccontextmanager

import httpx
import pytest

from web_search_sdk.utils.http import _DEFAULT_UA, fetch_text

from .conftest import show

# -------------------------- flaky transport helper -------------------------

captured_headers = []


class FlakyTransport(httpx.AsyncBaseTransport):
    """First request fails (500), second succeeds (200)."""

    def __init__(self):
        self.calls = 0

    async def handle_async_request(self, request):
        self.calls += 1
        captured_headers.append(request.headers.get("User-Agent"))
        if self.calls == 1:
            return httpx.Response(500, text="error")
        return httpx.Response(200, text="ok")


flaky_transport = FlakyTransport()


@asynccontextmanager
async def dummy_ctx(**kwargs):
    client = httpx.AsyncClient(transport=flaky_transport, headers=kwargs.get("headers"))
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_fetch_text_retry_and_headers(monkeypatch):
    # Patch the internal factory so we inject our dummy client
    from web_search_sdk.utils import http as http_mod

    monkeypatch.setattr(http_mod, "get_async_client", dummy_ctx)

    text = await fetch_text("http://example.com", retries=1)
    show("HTTP Retry", "fetch_text retry + UA", "Input  : http://example.com", f"Output : {text}")

    assert text == "ok"
    assert flaky_transport.calls == 2
    assert captured_headers[0] in _DEFAULT_UA
    assert captured_headers[1] in _DEFAULT_UA
