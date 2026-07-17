"""
Unit tests for enhanced web search SDK functions.
"""

from unittest.mock import AsyncMock, patch

import pytest

from web_search_sdk.scrapers.article_extractor import extract_article_content
from web_search_sdk.scrapers.base import ScraperContext
from web_search_sdk.scrapers.duckduckgo_enhanced import ddg_search_and_parse


class TestExtractArticleContent:
    """Test the extract_article_content function."""

    @pytest.mark.asyncio
    async def test_extract_article_content_success(self):
        """Test successful article extraction."""
        # Mock HTML content for a CNBC-like article
        mock_html = """
        <html>
        <head>
            <title>Bitcoin hits new high above $120,000</title>
            <meta name="author" content="Dylan Butts">
            <meta property="article:published_time" content="2025-07-14T10:30:00Z">
        </head>
        <body>
            <nav>Navigation menu</nav>
            <header>Header content</header>
            <main>
                <article>
                    <h1>Bitcoin hits new high above $120,000</h1>
                    <div class="author">By Dylan Butts</div>
                    <div class="content">
                        <p>The largest cryptocurrency by market capitalization traded above $120,000 to set a new record high on Monday.</p>
                        <p>Bitcoin's rally has been fueled by strong ETF inflows and growing institutional adoption.</p>
                    </div>
                </article>
            </main>
            <footer>Footer content</footer>
        </body>
        </html>
        """

        with patch(
            "web_search_sdk.scrapers.article_extractor._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_html

            result = await extract_article_content("https://www.cnbc.com/test-article")

            assert result["title"] == "Bitcoin hits new high above $120,000"
            assert "largest cryptocurrency" in result["content"]
            assert "Bitcoin's rally" in result["content"]
            assert result["author"] == "Dylan Butts"
            assert result["publish_date"] == "2025-07-14"
            assert result["source"] == "CNBC"
            assert "Bitcoin hits new high above $120,000" in result["summary"]

    @pytest.mark.asyncio
    async def test_extract_article_content_invalid_url(self):
        """Test article extraction with invalid URL."""
        with patch(
            "web_search_sdk.scrapers.article_extractor._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Connection failed")

            # The function should raise the exception, so we expect it
            with pytest.raises(Exception, match="Connection failed"):
                await extract_article_content("https://invalid-url.com/article")

    @pytest.mark.asyncio
    async def test_extract_article_content_empty_content(self):
        """Test article extraction with empty content."""
        with patch(
            "web_search_sdk.scrapers.article_extractor._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = "<html><body></body></html>"

            result = await extract_article_content("https://www.example.com/empty")

            # With empty HTML, we should get None or empty values
            assert result["title"] is None or result["title"] == "No title found"
            assert result["content"] is None or len(result["content"]) == 0
            assert result["author"] is None or result["author"] == "Unknown"
            assert result["publish_date"] is None or result["publish_date"] == "Unknown"
            assert result["source"] == "EXAMPLE"  # Source extraction returns uppercase


class TestDuckDuckGoSearchEnhanced:
    """Test the ddg_search_and_parse function."""

    @pytest.mark.asyncio
    async def test_duckduckgo_search_enhanced_success(self):
        """Test successful enhanced DuckDuckGo search."""
        # Mock HTML content for DuckDuckGo results
        mock_html = """
        <html>
        <body>
            <div class="result">
                <a class="result__a" href="https://www.cnbc.com/bitcoin-article">Bitcoin hits new high above $120,000</a>
                <div class="result__snippet">Bitcoin traded above $120,000 to set a new record high on Monday, fueled by strong ETF inflows.</div>
            </div>
            <div class="result">
                <a class="result__a" href="https://www.bloomberg.com/crypto-news">Crypto Market Update</a>
                <div class="result__snippet">Latest developments in the cryptocurrency market and trading analysis.</div>
            </div>
        </body>
        </html>
        """

        with patch(
            "web_search_sdk.scrapers.duckduckgo_enhanced._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_html

            ctx = ScraperContext()
            result = await ddg_search_and_parse("bitcoin", ctx)

            assert "links" in result
            assert "tokens" in result
            assert "results" in result
            assert len(result["results"]) == 2

            # Check first result
            first_result = result["results"][0]
            assert "Bitcoin hits new high" in first_result["title"]
            assert "Bitcoin traded above $120,000" in first_result["snippet"]
            assert first_result["url"] == "https://www.cnbc.com/bitcoin-article"
            assert first_result["source"] == "CNBC"

            # Check second result
            second_result = result["results"][1]
            assert "Crypto Market Update" in second_result["title"]
            assert "Latest developments" in second_result["snippet"]
            assert second_result["url"] == "https://www.bloomberg.com/crypto-news"
            assert second_result["source"] == "BLOOMBERG"  # Source extraction returns uppercase

    @pytest.mark.asyncio
    async def test_duckduckgo_search_enhanced_no_results(self):
        """Test enhanced search with no results."""
        with patch(
            "web_search_sdk.scrapers.duckduckgo_enhanced._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = "<html><body><div>No results found</div></body></html>"

            ctx = ScraperContext()
            result = await ddg_search_and_parse("nonexistent_term", ctx)

            assert result["links"] == []
            assert result["tokens"] == []
            assert result["results"] == []

    @pytest.mark.asyncio
    async def test_duckduckgo_search_enhanced_error(self):
        """Test enhanced search with error."""
        with patch(
            "web_search_sdk.scrapers.duckduckgo_enhanced._fetch_html", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("Search failed")

            ctx = ScraperContext()
            result = await ddg_search_and_parse("bitcoin", ctx)

            assert result["status"] == "error"
            assert result["error"] == "Exception"
            assert result["items"] == []


class TestEnhancedSearchIntegration:
    """Test integration between enhanced functions."""

    @pytest.mark.asyncio
    async def test_search_and_parse_enhanced_fallback(self):
        """Test that enhanced search_and_parse falls back to basic when enhanced fails."""
        from web_search_sdk.scrapers.search import search_and_parse

        # Mock enhanced search to fail
        with patch(
            "web_search_sdk.scrapers.duckduckgo_enhanced.ddg_search_and_parse",
            new_callable=AsyncMock,
        ) as mock_enhanced:
            mock_enhanced.side_effect = Exception("Enhanced search failed")

            # Mock basic search to succeed
            with patch(
                "web_search_sdk.scrapers.search.search_and_parse_basic", new_callable=AsyncMock
            ) as mock_basic:
                mock_basic.return_value = {"links": ["https://example.com"], "tokens": ["test"]}

                ctx = ScraperContext()
                result = await search_and_parse("test", ctx)

                assert result["links"] == ["https://example.com"]
                assert result["tokens"] == ["test"]
                assert "results" not in result  # Basic version doesn't have results


if __name__ == "__main__":
    pytest.main([__file__])
