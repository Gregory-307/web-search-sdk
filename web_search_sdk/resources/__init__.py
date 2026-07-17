"""Resource package exposing common data files."""

from pathlib import Path

__all__ = ["stopwords"]

_STOPWORD_PATH = Path(__file__).with_suffix("").parent / "stopwords.txt"
if _STOPWORD_PATH.exists():
    stopwords = _STOPWORD_PATH.read_text(encoding="utf-8").splitlines()
else:
    stopwords = []
