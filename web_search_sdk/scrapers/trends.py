"""Google Trends scraper (functional).

Uses the `pytrends` unofficial API to fetch interest-over-time data for a
single term. Because pytrends is synchronous, we wrap calls in
`asyncio.to_thread` so that the public API remains asynchronous.
"""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Callable

import pandas as pd
from pytrends.request import TrendReq

__all__ = ["interest_over_time", "batch_interest_over_time"]

# Deprecation notice – migrate to trends-sdk repo
warnings.warn(
    "scrapers.trends is deprecated; migrate to trends-sdk repo",
    DeprecationWarning,
    stacklevel=2,
)


def _interest_over_time_sync(term: str, timeframe: str, geo: str) -> pd.DataFrame:
    """Blocking helper executed in a thread."""
    pytrend = TrendReq(hl="en-US", tz=360)
    pytrend.build_payload([term], cat=0, timeframe=timeframe, geo=geo)
    df = pytrend.interest_over_time()
    return df


async def interest_over_time(
    term: str,
    timeframe: str = "today 12-m",
    geo: str = "",
) -> pd.DataFrame:
    """Return a pandas DataFrame with Google Trends interest over time."""
    loop = asyncio.get_running_loop()
    df: pd.DataFrame = await loop.run_in_executor(
        None, _interest_over_time_sync, term, timeframe, geo
    )
    return df


async def batch_interest_over_time(
    terms: list[str],
    *,
    timeframe: str = "today 12-m",
    geo: str = "",
    tracker: Callable[[str, pd.DataFrame | None], None] = None,
) -> dict[str, pd.DataFrame]:
    """Fetch trends for many *terms* sequentially.

    Parameters
    ----------
    terms : list[str]
    timeframe, geo : passed through to `interest_over_time`.
    tracker : optional callback invoked as ``tracker(term, df)`` after each
              fetch (df may be None if the request failed).

    Returns dict mapping term→DataFrame (empty DataFrame for failures).
    """
    result: dict[str, pd.DataFrame] = {}
    for term in terms:
        try:
            df = await interest_over_time(term, timeframe=timeframe, geo=geo)
        except Exception:
            df = pd.DataFrame()
        result[term] = df
        if tracker is not None:
            tracker(term, df if not df.empty else None)
    return result
