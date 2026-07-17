"""Offline acceptance tests for truthful provider and contract output."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from web_search_sdk.events import text_event_from_search_item
from web_search_sdk.models import SearchItem, SearchResponse, SearchStatus
from web_search_sdk.scrapers.article_extractor import clean_text
from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.scrapers.duckduckgo_enhanced import ddg_search_and_parse
from web_search_sdk.scrapers.news import _parse_rss_structured

FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "text_event_web_v1.json"


def test_search_response_rejects_untruthful_statuses() -> None:
    with pytest.raises(ValidationError, match="success requires"):
        SearchResponse(source="test", query="btc", status=SearchStatus.SUCCESS)
    with pytest.raises(ValidationError, match="blocked requires"):
        SearchResponse(source="test", query="btc", status=SearchStatus.BLOCKED)
    with pytest.raises(ValidationError, match="error requires"):
        SearchResponse(source="test", query="btc", status=SearchStatus.ERROR)
    item = SearchItem(source="test", text="result", rank=1)
    with pytest.raises(ValidationError, match="non-success status"):
        SearchResponse(source="test", query="btc", status=SearchStatus.EMPTY, items=[item])


def test_google_news_preserves_per_item_url_and_publication_time() -> None:
    xml = """
    <rss><channel><item>
      <title>Bitcoin (BTC) rallies</title>
      <link>https://example.com/markets/bitcoin</link>
      <pubDate>Thu, 16 Jul 2026 14:30:00 GMT</pubDate>
      <source>Example Markets</source>
      <description><![CDATA[Spot ETF inflows accelerate.]]></description>
    </item></channel></rss>
    """

    result = _parse_rss_structured(xml, term="btc", top_n=5)

    assert result["status"] == "success"
    assert result["items"] == [
        {
            "source": "google_news",
            "title": "Bitcoin (BTC) rallies",
            "text": "Spot ETF inflows accelerate.",
            "url": "https://example.com/markets/bitcoin",
            "published_at": "2026-07-16T14:30:00Z",
            "publisher": "Example Markets",
            "rank": 1,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("html", "expected_status"),
    [
        ("<html><body><p>No results found</p></body></html>", "empty"),
        ("<html><body><form id='challenge-form'>Are you a robot?</form></body></html>", "blocked"),
    ],
)
async def test_duckduckgo_distinguishes_empty_and_blocked(
    html: str,
    expected_status: str,
) -> None:
    with patch(
        "web_search_sdk.scrapers.duckduckgo_enhanced._fetch_html",
        new=AsyncMock(return_value=html),
    ):
        result = await ddg_search_and_parse("btc", ScraperContext())

    assert result["status"] == expected_status
    assert result["items"] == []
    assert (result["blocked_reason"] is not None) is (expected_status == "blocked")


def test_search_item_converts_exactly_to_golden_text_event() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    item = SearchItem(
        source="google_news",
        title="Bitcoin ETF inflows",
        text="Bitcoin (BTC) rallies as spot ETF inflows accelerate",
        url="https://example.com/markets/bitcoin-etf-inflows",
        published_at=datetime(2026, 7, 16, 14, 30, tzinfo=UTC),
        publisher="Example Markets",
        rank=1,
    )

    first = text_event_from_search_item(
        item,
        collected_at=datetime(2026, 7, 16, 14, 31, tzinfo=UTC),
        asset_mentions=["$btc"],
        provider_id="article-001",
        query_alias="btc-market-news",
        parser_version="1.0.0",
    ).model_dump(mode="json")
    second = text_event_from_search_item(
        item,
        collected_at=datetime(2026, 7, 16, 14, 31, tzinfo=UTC),
        asset_mentions=["BTC"],
        provider_id="article-001",
        query_alias="btc-market-news",
        parser_version="1.0.0",
    ).model_dump(mode="json")

    assert first == expected
    assert second == first


def test_missing_publication_time_records_fallback() -> None:
    item = SearchItem(source="duckduckgo", text="BTC market update", rank=1)
    event = text_event_from_search_item(
        item,
        collected_at=datetime(2026, 7, 16, 14, 31, tzinfo=UTC),
        query_alias="btc",
    )

    assert event.published_at is None
    assert event.provenance["event_time_fallback"] == "collected_at"


def test_text_event_rejects_secret_shaped_metrics_and_invalid_assets() -> None:
    item = SearchItem(source="duckduckgo", text="BTC market update", rank=1)
    kwargs = {
        "collected_at": datetime(2026, 7, 16, 14, 31, tzinfo=UTC),
        "query_alias": "btc",
    }

    with pytest.raises(ValidationError, match="secret-bearing"):
        text_event_from_search_item(item, extra_metrics={"apiKey": "redacted"}, **kwargs)
    with pytest.raises(ValidationError, match="invalid asset"):
        text_event_from_search_item(item, asset_mentions=["BTC/USDT"], **kwargs)


def test_clean_text_preserves_financial_parentheticals() -> None:
    assert "Bitcoin (BTC)" in clean_text("Bitcoin (BTC) rallied after the filing.")


def test_ordinary_package_import_is_warning_free_and_lazy() -> None:
    code = (
        "import sys, warnings; "
        "warnings.simplefilter('error', DeprecationWarning); "
        "import web_search_sdk; "
        "assert 'web_search_sdk.browser' not in sys.modules; "
        "assert 'web_search_sdk.scrapers.duckduckgo_web' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=Path.cwd())
