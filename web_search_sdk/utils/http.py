"""HTTP helper utilities built around httpx.AsyncClient.

Goals
-----
1. Centralise retry/back-off logic so individual scrapers stay lean.
2. Provide random User-Agent rotation with an optional custom list.
3. Support optional proxy configuration.

All helpers are *functional*; no classes are exposed.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import TypeVar

import httpx

from .logging import get_logger

T = TypeVar("T")

OFFLINE_MODE = os.getenv("OFFLINE_MODE") in {"1", "true", "True"}

# Helper used only when OFFLINE_MODE enabled ------------------------------------------------
if OFFLINE_MODE:
    _FIXTURE_DIR = os.getenv("OFFLINE_FIXTURES", "tests/fixtures")

    def _fixture_for_url(url: str) -> str:
        """Return cached HTML fixture for *url* or a generic placeholder.

        The mapping strategy is intentionally simple – the caller can set
        OFFLINE_FIXTURES to a directory containing files named by the *netloc*
        component (e.g. ``example.com.html``).  When no matching file is
        found we fall back to a short placeholder so downstream parsers still
        receive syntactically valid HTML.
        """
        import pathlib
        import textwrap
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        fname = f"{parsed.netloc}.html" if parsed.netloc else "fixture.html"
        path = pathlib.Path(_FIXTURE_DIR, fname)
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
        # Generic stub – make sure it is HTML so BeautifulSoup etc. work
        return textwrap.dedent(
            f"""
            <html>
                <head><title>OFFLINE MODE</title></head>
                <body><p>Offline fixture for {url}</p></body>
            </html>
            """
        )


logger = get_logger("utils.http")

__all__ = ["get_async_client", "fetch_text", "rate_limited"]

# ---------------------------------------------------------------------------
# Default UA list (very small; caller can supply custom list)
# ---------------------------------------------------------------------------

_DEFAULT_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@asynccontextmanager
async def get_async_client(
    *,
    timeout: float = 20.0,
    proxy: str | None = None,
    headers: dict[str, str] | None = None,
    ca_file: str | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Yield a configured `httpx.AsyncClient`.

    Parameters
    ----------
    timeout:  connection/read timeout seconds (applies to both connect & read)
    proxy:    optional proxy URL  (e.g. "http://user:pass@proxy:port")
    headers:  base headers applied to every request (e.g. Accept-Language)
    """
    client = httpx.AsyncClient(
        timeout=timeout,
        proxy=proxy,
        headers=headers,
        follow_redirects=True,
        verify=ca_file or True,
    )
    try:
        yield client
    finally:
        await client.aclose()


async def fetch_text(
    url: str,
    *,
    retries: int = 2,
    timeout: float = 20.0,
    proxy: str | None = None,
    headers: dict[str, str] | None = None,
    user_agents: list[str] | None = None,
    ca_file: str | None = None,
    scraper: str = "http",
) -> str:
    """Fetch a URL and return `response.text` with retry/backoff.

    Automatically injects a random UA if provided.
    """
    # ------------------------------------------------------------------
    # Offline stub: short-circuit *before* any network calls --------------
    # ------------------------------------------------------------------
    if OFFLINE_MODE:
        logger.info("offline_fetch", url=url)
        return _fixture_for_url(url)

    headers = headers.copy() if headers else {}
    if user_agents is None:
        user_agents = _DEFAULT_UA
    headers.setdefault("User-Agent", random.choice(user_agents))

    for attempt in range(retries + 1):
        try:
            logger.debug("fetch", url=url, attempt=attempt)
            async with get_async_client(
                timeout=timeout, proxy=proxy, headers=headers, ca_file=ca_file
            ) as client:
                start = time.perf_counter()
                resp = await client.get(url)
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                resp.raise_for_status()
                # Telemetry ---------------------------------------------------
                if os.getenv("LOG_SCRAPERS") or os.getenv("DEBUG_SCRAPERS") in {
                    "1",
                    "true",
                    "True",
                }:
                    # Emit two log events: legacy "telemetry" (kept for backward compat)
                    # and an httpx-style "response" event so tests can assert on
                    # `body_len` without relying on the httpx patch when the client
                    # is monkey-patched.
                    logger.info(
                        "telemetry",
                        url=url,
                        status=resp.status_code,
                        elapsed_ms=elapsed_ms,
                        content_len=len(resp.content),
                        scraper=scraper,
                    )

                    from .logging import get_logger as _get_logger  # local import to avoid cycles

                    _get_logger("httpx").info(
                        "response",
                        status=resp.status_code,
                        url=url,
                        body_len=len(resp.content),
                    )
                return resp.text
        except Exception as exc:
            logger.warning("fetch_error", url=url, attempt=attempt, error=str(exc))
            if attempt >= retries:
                raise
            # Exponential backoff: 0.5, 1.0, 2.0 …
            await asyncio.sleep(0.5 * 2**attempt)

    # Should never reach here
    raise RuntimeError("fetch_text: exceeded retries without exception")


# ---------------------------------------------------------------------------
# Rate limiting utilities
# ---------------------------------------------------------------------------


def rate_limited(*, calls: int, period: float):
    """Decorator limiting *calls* within *period* seconds per coroutine group.

    Usage::

        from web_search_sdk.utils.http import rate_limited

        @rate_limited(calls=5, period=1)  # 5 calls per second
        async def fetch(...):
            ...
    """

    bucket = calls
    reset_at = time.monotonic() + period
    lock = asyncio.Lock()

    def decorator(fn: Callable[..., Awaitable[T]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> T:  # type: ignore[override]
            nonlocal bucket, reset_at
            async with lock:
                now = time.monotonic()
                if now >= reset_at:
                    bucket = calls
                    reset_at = now + period
                if bucket == 0:
                    sleep_for = reset_at - now
                    await asyncio.sleep(max(sleep_for, 0))
                    bucket = calls - 1
                    reset_at = time.monotonic() + period
                else:
                    bucket -= 1
            return await fn(*args, **kwargs)

        return wrapper

    return decorator
