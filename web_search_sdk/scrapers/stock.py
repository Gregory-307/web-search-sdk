"""Stock price fetcher (functional).

Uses the `yfinance` library to download OHLCV data for a ticker symbol.
This module is kept synchronous under the hood but exposed via an async
wrapper to align with the rest of the SDK.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pandas as pd
import yfinance as yf

__all__ = ["fetch_stock_data"]


async def _fetch_sync(
    symbol: str,
    start: date | str | None = None,
    end: date | str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=False)
    if not df.empty:
        df.reset_index(inplace=True)
    return df


async def fetch_stock_data(
    symbol: str,
    start: date | str | None = None,
    end: date | str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Return historical OHLC data for *symbol* as a DataFrame.

    If *start*/*end* are strings they can be in any format supported by
    `pandas.to_datetime`, including natural phrases like "2023-01-15".
    """
    loop = asyncio.get_running_loop()
    df: pd.DataFrame = await loop.run_in_executor(
        None,
        lambda: yf.download(symbol, start=start, end=end, interval=interval, progress=False),
    )
    if not df.empty:
        df.reset_index(inplace=True)
    return df
