"""Offline import and contract smoke test for an installed SDK."""

from __future__ import annotations

from datetime import UTC, datetime

from web_search_sdk import SearchItem, text_event_from_search_item


def main() -> None:
    item = SearchItem(
        source="google_news",
        title="Bitcoin market update",
        text="Bitcoin (BTC) rallies as spot ETF inflows accelerate",
        url="https://example.com/markets/bitcoin",
        published_at=datetime(2026, 7, 16, 14, 30, tzinfo=UTC),
        publisher="Example Markets",
        rank=1,
    )
    event = text_event_from_search_item(
        item,
        collected_at=datetime(2026, 7, 16, 14, 31, tzinfo=UTC),
        asset_mentions=["BTC"],
        provider_id="smoke-001",
        query_alias="offline-smoke",
    )
    print(event.model_dump_json())


if __name__ == "__main__":
    main()
