# Web Search SDK

An async Python 3.12 SDK for collecting public web text and turning it into
truthful, structured records for downstream sentiment analysis.

The core install is HTTP-only. Browser automation and market-data helpers are
optional extras, so ordinary package imports stay lightweight and do not start
or import a browser stack.

## Native setup

Install [uv](https://docs.astral.sh/uv/) once, then run from this repository:

```bash
uv sync --locked --extra test
uv run pytest
```

Optional capabilities are installed explicitly:

```bash
# Browser-backed scrapers
uv sync --locked --extra test --extra browser
uv run playwright install firefox

# Legacy trends and market-data helpers
uv sync --locked --extra test --extra market
```

No path injection is required. Run scripts and tests through `uv run`, or
activate the repository-local `.venv` created by uv.

## Structured search output

Google News and DuckDuckGo return a common shape with an explicit provider
outcome:

```python
import asyncio

from web_search_sdk import google_news


async def main() -> None:
    response = await google_news("bitcoin ETF", top_n=10)
    print(response["status"])  # success, empty, blocked, or error
    for item in response["items"]:
        print(item["published_at"], item["url"], item["text"])


asyncio.run(main())
```

Every item contains its own source, text, URL, publication time, publisher,
and rank. Provider failure details are categories such as an exception class;
credentials, proxy URLs, and response bodies are not included.

The normalized models are available directly:

```python
from web_search_sdk import SearchItem, SearchResponse, SearchStatus
```

## Sentiment-suite contract

Convert a normalized result to the versioned `TextEvent` boundary without
importing another repository:

```python
from datetime import datetime, timezone

from web_search_sdk import SearchItem, text_event_from_search_item

item = SearchItem(
    source="google_news",
    text="Bitcoin (BTC) rallies as spot ETF inflows accelerate",
    url="https://example.com/markets/bitcoin",
    published_at=datetime(2026, 7, 16, 14, 30, tzinfo=timezone.utc),
    rank=1,
)
event = text_event_from_search_item(
    item,
    collected_at=datetime.now(timezone.utc),
    asset_mentions=["BTC"],
    query_alias="btc-market-news",
)
print(event.model_dump_json())
```

The adapter produces schema `1.0.0`, UTC timestamps, normalized asset symbols,
a source-namespaced event ID, and a deterministic SHA-256 content hash. If a
provider has no publication time, provenance explicitly records the use of
collection time as the downstream event-time fallback.

The reference fixture is
[`tests/fixtures/contracts/text_event_web_v1.json`](tests/fixtures/contracts/text_event_web_v1.json).

## Public helpers

| Helper | Purpose | Default transport |
| --- | --- | --- |
| `google_news` | Structured Google News RSS items | HTTP |
| `ddg_search_and_parse` | Structured DuckDuckGo results | HTTP |
| `search_and_parse` | DuckDuckGo-first search with fallback | HTTP |
| `related_words` | RelatedWords/Datamuse terms | HTTP |
| `wikipedia` | Structured Wikipedia article data | HTTP |
| `wikipedia_top_words` | Legacy-compatible Wikipedia tokens | HTTP |
| `google_web_top_words` | Google SERP tokens | Optional browser |
| `extract_article_content` | General article extraction | HTTP, optional browser |

All helpers accept a `ScraperContext` where applicable:

```python
from web_search_sdk.scrapers.base import ScraperContext

context = ScraperContext(timeout=15, retries=2, proxy=None, debug=False)
```

## Testing and CI parity

The default suite is deterministic and excludes tests marked `live`:

```bash
uv sync --locked --extra test
uv run ruff check web_search_sdk tests smoke_test.py
uv run ruff format --check web_search_sdk tests smoke_test.py
uv run pytest
uv build
```

Run external-provider diagnostics only when intentionally testing network
behaviour:

```bash
uv run pytest -m live
```

Live tests are diagnostic: provider throttling, blocking, and layout changes
are external conditions rather than proof that the offline SDK is broken.

## Package boundaries

- Core: HTTP acquisition, parsing, structured models, and contract conversion.
- `browser` extra: Playwright, Selenium, and webdriver-manager.
- `market` extra: pandas, pytrends, and yfinance legacy helpers.
- `test` extra: pytest, Ruff, coverage, and build tooling.

The wheel includes the package root, nested scraper modules, utilities, and the
stop-word resource. CI installs the wheel outside the source tree to catch
packaging regressions.
