"""Base helpers for functional scrapers.

The project avoids heavy OOP – instead we expose small, composable
functions and a lightweight dispatch mechanism.
"""

from __future__ import annotations

import asyncio
import functools
import random
from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "ScrapeFn",
    "ParseFn",
    "ScraperContext",
    "run_scraper",
    "gather_scrapers",
]

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------


class ScrapeFn(Protocol):
    """Low-level coroutine that fetches raw text for a single term/url."""

    async def __call__(self, term: str, ctx: ScraperContext) -> str:  # pragma: no cover
        ...


class ParseFn(Protocol):
    """Pure function that turns raw HTML/text into structured data."""

    def __call__(self, raw: str, term: str, ctx: ScraperContext) -> Any:  # pragma: no cover
        ...


@dataclass
class ScraperContext:
    """Shared, immutable configuration passed to fetch & parse funcs."""

    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 20.0
    retries: int = 2
    user_agents: list[str] | None = None
    proxy: str | None = None

    # If True, scraper may launch a headless browser (Selenium) as last resort
    use_browser: bool = False

    # When True (or env DEBUG_SCRAPERS=1) all HTTP traffic is logged verbosely.
    debug: bool = False

    # Max depth for crawling (e.g., link following)
    max_depth: int = 1

    # Preferred browser backend when use_browser=True ("selenium" | "playwright")
    browser_type: str = "selenium"

    def choose_ua(self) -> str | None:
        if not self.user_agents:
            return None
        return random.choice(self.user_agents)


# ---------------------------------------------------------------------------
# Sync→async helper
# ---------------------------------------------------------------------------


async def run_in_thread(fn, *args, **kwargs):
    """Run blocking *fn* in a thread, return its result asynchronously."""
    loop = asyncio.get_running_loop()
    partial = functools.partial(fn, *args, **kwargs)
    return await loop.run_in_executor(None, partial)


# ---------------------------------------------------------------------------
# Runner helpers (functional – no classes)
# ---------------------------------------------------------------------------


async def run_scraper(
    term: str,
    fetch: ScrapeFn,
    parse: ParseFn,
    ctx: ScraperContext | None = None,
) -> Any:
    """End-to-end run for a single term.

    fetch(term) -> raw_text  |  parse(raw_text) -> structured_data
    """
    if ctx is None:
        ctx = ScraperContext()

    raw: str = await fetch(term, ctx)
    return parse(raw, term, ctx)


async def gather_scrapers(
    terms: list[str],
    fetch: ScrapeFn,
    parse: ParseFn,
    ctx: ScraperContext | None = None,
    parallelism: int = 5,
) -> list[Any]:
    """Convenience helper to fan-out scraping across many terms."""
    if ctx is None:
        ctx = ScraperContext()

    sem = asyncio.Semaphore(parallelism)

    async def _runner(t: str):
        async with sem:
            return await run_scraper(t, fetch, parse, ctx)

    return await asyncio.gather(*[_runner(t) for t in terms])
