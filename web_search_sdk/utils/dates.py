"""Date parsing helpers.

`parse_fuzzy_date` accepts strings like "2020-01-15", "2020/1/15",
"-30 days" (meaning today minus 30 days) and returns a `datetime.date`.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

__all__ = ["parse_fuzzy_date"]

_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
_DAYS_RE = re.compile(r"^-?(\d+)\s*days?$", re.IGNORECASE)


def parse_fuzzy_date(text: str | date) -> date:
    """Parse a human-friendly date string into a `datetime.date`.

    Examples
    --------
    >>> parse_fuzzy_date("2020-04-01")
    datetime.date(2020, 4, 1)
    >>> parse_fuzzy_date("-7 days")
    datetime.date(<today_minus_7>)
    """
    if isinstance(text, date):
        # Already a date – cast away datetime.
        return text

    text = text.strip()

    # ISO / common formats  YYYY-MM-DD or YYYY/M/D
    m = _DATE_RE.match(text)
    if m:
        year, month, day = map(int, m.groups())
        return date(year, month, day)

    # Relative days like "-30 days"
    m = _DAYS_RE.match(text.replace("-", "")) if text.startswith("-") else _DAYS_RE.match(text)
    if m and text.startswith("-"):
        days = int(m.group(1))
        return date.today() - timedelta(days=days)

    raise ValueError(f"Unrecognised date format: {text}")
