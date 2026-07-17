"""Legacy RelatedWords scraper using simple HTML parsing (synchronous).
Intentionally preserved from the original code path for cases where the new
JSON API is blocked.

DEPRECATED: This module is kept for internal fallback only. Use the async
related.py module instead.

INTERNAL USE ONLY: Do not import this module in user code.
"""

from __future__ import annotations

import json
import os
import random
import re
import warnings

import requests

from ..utils.http import _DEFAULT_UA

warnings.warn(
    "related_legacy module is deprecated and will be removed in a future version. "
    "Use the async related module instead.",
    DeprecationWarning,
    stacklevel=2,
)

HTML_URL = "https://relatedwords.org/relatedto/{}"
API_URL = "https://relatedwords.org/api/related?term={}&max=50"

__all__ = ["related_words_sync"]


def _ensure_headers(hdrs: dict | None) -> dict:
    hdrs = hdrs.copy() if hdrs else {}
    hdrs.setdefault("User-Agent", random.choice(_DEFAULT_UA))
    hdrs.setdefault("Accept", "application/json, text/html;q=0.9,*/*;q=0.8")
    hdrs.setdefault("Accept-Language", "en-US,en;q=0.9")
    return hdrs


def related_words_sync(term: str, headers: dict | None = None, timeout: float = 20.0) -> list[str]:
    """Return related words using JSON API; fallback to HTML title parse."""
    headers = _ensure_headers(headers)

    # 1. Try JSON endpoint --------------------------------------------------
    api_url = API_URL.format(requests.utils.quote(term))
    if os.getenv("DEBUG_SCRAPERS") in {"1", "true", "True"}:
        print(f"[RelatedWords-JSON] GET {api_url}")

    try:
        r = requests.get(api_url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            body = r.text.lstrip(")]}',\n")  # strip JSONP prefix if present
            data = json.loads(body)
            words = [item["word"] for item in data if "word" in item]
            if words:
                return words
    except Exception:
        pass

    # 2. Fallback: parse <title> from HTML page -----------------------------
    html_url = HTML_URL.format(term.replace(" ", "%20"))
    if os.getenv("DEBUG_SCRAPERS") in {"1", "true", "True"}:
        print(f"[RelatedWords-HTML] GET {html_url}")

    resp = requests.get(html_url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    match = re.search(r"related words:\s*(.+?)</title>", resp.text, re.I)
    if match:
        part = match.group(1)
        # remove bracket note like [405 more]
        part = re.sub(r"\s*\[.*?more\]", "", part)
        return [w.strip() for w in part.split() if w.strip()]

    # Ultimate fallback: JS-less page; return empty list
    return []
