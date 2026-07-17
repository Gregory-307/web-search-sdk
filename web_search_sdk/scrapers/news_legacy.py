"""Legacy Google News HTML scraper.
Searches the standard news.google.com/search page and extracts headline text.

DEPRECATED: This module is kept for internal fallback only. Use the async
news.py module instead.

INTERNAL USE ONLY: Do not import this module in user code.
"""

from __future__ import annotations

import os
import random
import re
import warnings
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

from ..utils.http import _DEFAULT_UA

warnings.warn(
    "news_legacy module is deprecated and will be removed in a future version. "
    "Use the async news module instead.",
    DeprecationWarning,
    stacklevel=2,
)

SEARCH_URL = "https://news.google.com/search?q={}&hl=en-US&gl=US&ceid=US:en"
RSS_URL = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
TOKEN_RE = re.compile(r"[A-Za-z]{2,}")

# Load stop-word list -------------------------------------------------------
_stopwords_path = Path(__file__).resolve().parent.parent / "resources" / "stopwords.txt"

try:
    _STOPWORDS: set[str] = {
        line.strip().lower()
        for line in _stopwords_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
except FileNotFoundError:
    _STOPWORDS = set()


def _tokenise(text: str) -> list[str]:
    """Return lowercase alpha tokens (≥2 chars) from *text*."""
    return TOKEN_RE.findall(text.lower())


__all__ = ["top_words_sync"]


def top_words_sync(
    term: str,
    top_n: int = 10,
    headers: dict | None = None,
    timeout: float = 20.0,
) -> list[str]:
    """Blocking helper that returns *top_n* most common tokens from Google News.

    Strategy: RSS feed first (robust, JS-free).  If that yields no words we fall
    back to scraping the HTML shell page as a last resort.
    """

    hdrs = headers.copy() if headers else {}
    hdrs.setdefault("User-Agent", random.choice(_DEFAULT_UA))
    hdrs.setdefault("Accept-Language", "en-US,en;q=0.9")

    # 1️⃣ RSS feed (preferred) ------------------------------------------------
    rss_url = RSS_URL.format(requests.utils.quote(term))
    if os.getenv("DEBUG_SCRAPERS") in {"1", "true", "True"}:
        print(f"[GoogleNews-RSS] GET {rss_url}")

    try:
        r = requests.get(rss_url, headers=hdrs, timeout=timeout)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        titles = [item.findtext("title") for item in root.iter("item") if item.findtext("title")]
        tokens = [t for t in _tokenise(" ".join(titles)) if t not in _STOPWORDS]
        counter = Counter(tokens)
        words = [tok for tok, _ in counter.most_common(top_n)]
        if words:
            return words
    except Exception:
        # Continue to HTML fallback
        pass

    # 2️⃣ HTML search page fallback -----------------------------------------
    url = SEARCH_URL.format(requests.utils.quote(term))
    if os.getenv("DEBUG_SCRAPERS") in {"1", "true", "True"}:
        print(f"[GoogleNews-HTML] GET {url}")

    try:
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        headlines = [h.text.strip() for h in soup.select("article h3 a")]
        tokens = [t for t in _tokenise(" ".join(headlines)) if t not in _STOPWORDS]
        counter = Counter(tokens)
        return [tok for tok, _ in counter.most_common(top_n)]
    except Exception:
        return []
