"""Structured logging helper using structlog."""
# If structlog is unavailable (e.g., minimal runtime env) we fall back to a
# no-op shim that preserves the public API (get_logger) so callers continue
# to work without installing the extra dependency.

import logging
import os
from typing import Any

try:
    import httpx
    import requests
except ImportError:  # pragma: no cover – optional dependencies
    httpx = None
    requests = None

try:
    import structlog  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – optional dependency
    import types

    _shim_mod = types.ModuleType("structlog.processors")

    def _noop_processor(*_a, **_kw):
        return lambda logger, name, event_dict: event_dict  # type: ignore

    _shim_mod.TimeStamper = lambda *a, **kw: _noop_processor  # type: ignore
    _shim_mod.JSONRenderer = lambda *a, **kw: _noop_processor  # type: ignore

    _stdlib_mod = types.ModuleType("structlog.stdlib")

    class _LoggerFactory:  # noqa: D401 – simple shim
        def __call__(self, *args, **kwargs):  # type: ignore
            return logging.getLogger("shim")

    _stdlib_mod.LoggerFactory = _LoggerFactory

    class _StructlogShim(types.ModuleType):
        def get_logger(self, name=None):  # type: ignore
            return logging.getLogger(name)

        def configure(self, *args, **kwargs):  # type: ignore
            # No-op configuration in shim environment
            return None

        processors = _shim_mod  # type: ignore
        stdlib = _stdlib_mod  # type: ignore

    import sys

    structlog = _StructlogShim("structlog")  # type: ignore
    sys.modules["structlog"] = structlog
    sys.modules["structlog.processors"] = _shim_mod
    sys.modules["structlog.stdlib"] = _stdlib_mod

__all__ = ["get_logger"]


# Configure on first import only
_handler = logging.StreamHandler()
_formatter = logging.Formatter("%(message)s")
_handler.setFormatter(_formatter)
root = logging.getLogger()
if not root.handlers:
    root.addHandler(_handler)
    root.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Optional file output when DEBUG_SCRAPERS or LOG_SCRAPERS env vars are set
# ---------------------------------------------------------------------------

_log_path = None

# Explicit path wins
if os.getenv("LOG_SCRAPERS"):
    _log_path = os.getenv("LOG_SCRAPERS")
# Otherwise use default file when debug mode active
elif os.getenv("DEBUG_SCRAPERS") in {"1", "true", "True"}:
    _log_path = "scraper_debug.log"

if _log_path:
    try:
        _file_handler = logging.FileHandler(_log_path, encoding="utf-8")
        _file_handler.setFormatter(_formatter)
        root.addHandler(_file_handler)
    except Exception as _e:  # pragma: no cover – file system errors shouldn’t crash app
        # Fallback silently; logs will still appear on stdout.
        root.error("file_handler_error", path=_log_path, error=str(_e))

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

_LOGGER_CACHE = {}


def get_logger(name: str | None = None):
    # Return the same instance for identical names so monkeypatching methods on
    # the returned logger is reliable across separate calls (unit test helper).
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]
    logger = structlog.get_logger(name)
    _LOGGER_CACHE[name] = logger
    return logger


# ---------------------------------------------------------------------------
# HTTP logging patches (httpx and requests)
# ---------------------------------------------------------------------------


def _setup_httpx_logging():
    """Patch httpx.AsyncClient to log all requests/responses when DEBUG_SCRAPERS=1."""
    if not httpx or os.getenv("DEBUG_SCRAPERS") not in {"1", "true", "True"}:
        return

    if getattr(httpx, "_patched_for_logging", False):
        return

    _orig_send = httpx.AsyncClient.send

    async def _patched_send(self: httpx.AsyncClient, request: httpx.Request, *args, **kwargs):  # type: ignore[override]
        # Acquire logger lazily at call time so downstream monkey-patches on
        # `get_logger("httpx")` are respected (important for unit tests).
        logger = get_logger("httpx")
        logger.info(
            "request",
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
        )
        response = await _orig_send(self, request, *args, **kwargs)

        # read() consumes the stream only once – cache content, then assign back
        content = await response.aread()
        body_len = len(content)
        preview_text = None
        if os.getenv("DEBUG_TRACE") in {"1", "true", "True"}:
            preview_slice = content[:1024]
            try:
                preview_text = preview_slice.decode("utf-8", errors="replace")
            except Exception:
                preview_text = str(preview_slice)

        log_kwargs = {
            "status": response.status_code,
            "url": str(response.request.url),
            "headers": dict(response.headers),
            "body_len": body_len,
        }
        if preview_text is not None:
            log_kwargs["preview"] = preview_text

        logger.info("response", **log_kwargs)

        # Restore body for downstream consumers
        response._content = content  # type: ignore[attr-defined]
        response._content_consumed = True  # type: ignore[attr-defined]
        return response

    # Override class attribute directly; Python binds functions to instances automatically.
    httpx.AsyncClient.send = _patched_send  # type: ignore[assignment]
    httpx._patched_for_logging = True  # type: ignore[attr-defined]


def _setup_requests_logging():
    """Patch requests.Session to log all requests/responses when DEBUG_SCRAPERS=1."""
    if not requests or os.getenv("DEBUG_SCRAPERS") not in {"1", "true", "True"}:
        return

    if getattr(requests, "_patched_for_logging", False):
        return

    logger = get_logger("requests")
    _orig_request = requests.Session.request  # type: ignore[attr-defined]

    def _patched_request(self: requests.Session, method: str, url: str, *args: Any, **kwargs: Any):  # type: ignore[override]
        headers: dict[str, str] | None = kwargs.get("headers")
        logger.info("request", method=method, url=url, headers=headers or {})

        resp: requests.Response = _orig_request(self, method, url, *args, **kwargs)

        body_len = len(resp.content) if resp.content is not None else 0
        log_kwargs: dict[str, Any] = {
            "status": resp.status_code,
            "url": resp.url,
            "headers": dict(resp.headers),
            "body_len": body_len,
        }

        if os.getenv("DEBUG_TRACE") in {"1", "true", "True"}:
            preview = resp.text[:1024]
            log_kwargs["preview"] = preview

        logger.info("response", **log_kwargs)
        return resp

    requests.Session.request = _patched_request  # type: ignore[assignment]
    requests._patched_for_logging = True  # type: ignore[attr-defined]


# Auto-setup logging patches on import
_setup_httpx_logging()
_setup_requests_logging()
