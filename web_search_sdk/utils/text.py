"""Text processing helpers."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

# Load stopwords
_STOPWORDS_FILE = Path(__file__).resolve().parent.parent / "resources" / "stopwords.txt"
try:
    _STOPWORDS: set[str] = {
        line.strip().lower()
        for line in _STOPWORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
except FileNotFoundError:
    _STOPWORDS = set()

TOKEN_RE = re.compile(r"[A-Za-z]{2,}")

__all__ = ["tokenise", "remove_stopwords", "most_common"]


def tokenise(text: str) -> list[str]:
    """Return lowercase word tokens from *text*."""
    return TOKEN_RE.findall(text.lower())


def remove_stopwords(tokens: Iterable[str]) -> list[str]:
    """Filter out stop-words from *tokens*."""
    return [t for t in tokens if t not in _STOPWORDS]


def most_common(tokens: Iterable[str], n: int) -> list[str]:
    """Return the *n* most common tokens after stop-word removal."""
    filtered = remove_stopwords(tokens)
    return [tok for tok, _ in Counter(filtered).most_common(n)]
