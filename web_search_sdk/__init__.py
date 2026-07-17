"""Public API for the web-search SDK.

Scrapers are loaded on first access so importing :mod:`web_search_sdk` stays
lightweight and never triggers legacy deprecation warnings or browser imports.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.2.1"

_EXPORTS = {
    "SearchItem": ("web_search_sdk.models", "SearchItem"),
    "SearchResponse": ("web_search_sdk.models", "SearchResponse"),
    "SearchStatus": ("web_search_sdk.models", "SearchStatus"),
    "TextEventRecord": ("web_search_sdk.events", "TextEventRecord"),
    "text_event_from_search_item": (
        "web_search_sdk.events",
        "text_event_from_search_item",
    ),
    "related_words": ("web_search_sdk.scrapers.related", "related_words"),
    "wikipedia_top_words": ("web_search_sdk.scrapers.wikipedia", "wikipedia_top_words"),
    "wikipedia": ("web_search_sdk.scrapers.wikipedia", "wikipedia"),
    "wikipedia_raw": ("web_search_sdk.scrapers.wikipedia", "wikipedia_raw"),
    "google_news_top_words": ("web_search_sdk.scrapers.news", "google_news_top_words"),
    "google_news": ("web_search_sdk.scrapers.news", "google_news"),
    "google_news_raw": ("web_search_sdk.scrapers.news", "google_news_raw"),
    "google_web_top_words": ("web_search_sdk.scrapers.google_web", "google_web_top_words"),
    "extract_article_content": (
        "web_search_sdk.scrapers.article_extractor",
        "extract_article_content",
    ),
    "ddg_search_and_parse": (
        "web_search_sdk.scrapers.duckduckgo_enhanced",
        "ddg_search_and_parse",
    ),
    "ddg_search_raw": ("web_search_sdk.scrapers.duckduckgo_enhanced", "ddg_search_raw"),
    "search_and_parse": ("web_search_sdk.scrapers.search", "search_and_parse"),
    "browser": ("web_search_sdk.browser", None),
}

__all__ = [*_EXPORTS, "__version__"]


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:  # pragma: no cover - standard module protocol
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
