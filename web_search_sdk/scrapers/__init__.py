"""Lazy public scraper exports.

Submodules remain importable for compatibility, while ordinary package import
does not execute deprecated modules or optional browser stacks.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "related_words": ("web_search_sdk.scrapers.related", "related_words"),
    "wikipedia_top_words": ("web_search_sdk.scrapers.wikipedia", "wikipedia_top_words"),
    "wikipedia": ("web_search_sdk.scrapers.wikipedia", "wikipedia"),
    "wikipedia_raw": ("web_search_sdk.scrapers.wikipedia", "wikipedia_raw"),
    "google_news_top_words": ("web_search_sdk.scrapers.news", "google_news_top_words"),
    "google_news": ("web_search_sdk.scrapers.news", "google_news"),
    "google_news_raw": ("web_search_sdk.scrapers.news", "google_news_raw"),
    "google_web_top_words": ("web_search_sdk.scrapers.google_web", "google_web_top_words"),
    "duckduckgo_top_words": (
        "web_search_sdk.scrapers.duckduckgo_web",
        "duckduckgo_top_words",
    ),
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
    "duckduckgo_web": ("web_search_sdk.scrapers.duckduckgo_web", None),
    "paywall": ("web_search_sdk.scrapers.paywall", None),
}

__all__ = list(_EXPORTS)


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
