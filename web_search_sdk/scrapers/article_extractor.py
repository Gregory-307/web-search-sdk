"""General article content extraction.

This module provides a unified interface for extracting clean article content
from any URL, replacing the specific Bloomberg/CNBC functions with a more
general approach that can handle multiple site structures.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from web_search_sdk import browser as br
from web_search_sdk.utils.logging import get_logger

from .base import ScraperContext

logger = get_logger("ArticleExtractor")

__all__ = [
    "extract_article_content",
    "extract_metadata",
    "clean_text",
]


def _extract_title(soup: BeautifulSoup) -> str | None:
    """Extract article title from various HTML structures."""
    # Common title selectors
    title_selectors = [
        "h1",  # Most common
        "h1.article-title",
        "h1.headline",
        "title",  # Fallback to page title
        "meta[property='og:title']",  # Open Graph
        "meta[name='twitter:title']",  # Twitter Card
    ]

    for selector in title_selectors:
        element = soup.select_one(selector)
        if element:
            title = (
                element.get_text().strip() if element.name != "meta" else element.get("content", "")
            )
            if title and len(title) > 10:  # Reasonable title length
                return title

    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    """Extract author information from various HTML structures."""
    # Common author selectors
    author_selectors = [
        "meta[name='author']",
        "meta[property='article:author']",
        ".author",
        ".byline",
        ".author-name",
        "[data-author]",
        "span.author",
        "a.author",
    ]

    for selector in author_selectors:
        element = soup.select_one(selector)
        if element:
            author = (
                element.get_text().strip() if element.name != "meta" else element.get("content", "")
            )
            if author and len(author) > 2:
                return author

    return None


def _extract_date(soup: BeautifulSoup) -> str | None:
    """Extract publication date from various HTML structures."""
    # Common date selectors
    date_selectors = [
        "meta[property='article:published_time']",
        "meta[name='publish_date']",
        "meta[name='date']",
        ".date",
        ".publish-date",
        ".article-date",
        "time",
        "[datetime]",
    ]

    for selector in date_selectors:
        element = soup.select_one(selector)
        if element:
            if element.name == "meta":
                date_str = element.get("content", "")
            elif element.get("datetime"):
                date_str = element.get("datetime")
            else:
                date_str = element.get_text().strip()

            if date_str:
                # Try to parse and format the date
                try:
                    # Handle various date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                        try:
                            parsed_date = datetime.strptime(date_str[:19], fmt)
                            return parsed_date.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                except Exception:
                    pass

    return None


def _extract_source(url: str) -> str:
    """Extract source name from URL."""
    try:
        domain = urlparse(url).netloc
        # Remove www. prefix and get main domain
        source = domain.replace("www.", "").split(".")[0]
        return source.upper()
    except Exception:
        return "Unknown"


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Extract main article content, removing navigation and ads."""

    # Remove unwanted elements more aggressively
    for selector in [
        "nav",
        "header",
        "footer",
        "aside",
        ".navigation",
        ".menu",
        ".sidebar",
        ".advertisement",
        ".ad",
        ".ads",
        ".social-share",
        ".comments",
        "script",
        "style",
        "noscript",
        ".skip-navigation",
        ".site-header",
        ".site-footer",
        ".breadcrumb",
        ".breadcrumbs",
        ".related-articles",
        ".recommended",
        ".newsletter",
        ".subscribe",
        ".video-player",
        ".video-container",
        ".image-caption",
        ".caption",
        ".author-bio",
        ".author-info",
        ".article-meta",
        ".article-info",
        ".share-buttons",
        ".social-media",
        ".advertisement",
        ".sponsored",
        ".newsletter-signup",
        ".email-signup",
    ]:
        for element in soup.select(selector):
            element.decompose()

    # CNBC-specific content selectors
    cnbc_selectors = [
        ".ArticleBody-articleBody",
        ".ArticleBody-content",
        ".ArticleBody",
        ".article-body",
        ".story-body",
        ".article-content",
        ".post-content",
        ".entry-content",
    ]

    # Try CNBC-specific selectors first
    for selector in cnbc_selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if len(text) > 200:  # Reasonable content length
                return text

    # General content selectors
    general_selectors = [
        "article",
        "main",
        ".content",
        "#content",
        ".main-content",
        ".article",
        ".post",
        ".entry",
    ]

    # Try general content selectors
    for selector in general_selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(" ", strip=True)
            if len(text) > 200:  # Reasonable content length
                return text

    # Fallback: get body text but filter out navigation
    body = soup.find("body")
    if body:
        # Remove any remaining navigation-like elements
        for element in body.find_all(["nav", "header", "footer", "aside"]):
            element.decompose()
        return body.get_text(" ", strip=True)

    return ""


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    if not text:
        return ""

    # Remove navigation artifacts
    navigation_patterns = [
        r"Skip Navigation.*?Menu",
        r"Markets Business Investing Tech Politics Video Watchlist",
        r"Investing Club PRO Livestream",
        r"Key Points",
        r"Don\'t miss these insights from CNBC PRO",
        r"watch now VIDEO \d+:\d+",
        r"Closing Bell: Overtime",
        r"Subscribe to CNBC PRO",
        r"Subscribe to Investing Club",
        r"Licensing & Reprints",
        r"CNBC Councils",
        r"Select Personal Finance",
        r"CNBC on Peacock",
        r"Join the CNBC Panel",
        r"Supply Chain Values",
        r"Select Shopping",
        r"Closed Captioning",
        r"Digital Products",
        r"News Releases",
        r"Internships",
        r"Corrections",
        r"About CNBC",
        r"Ad Choices",
        r"Site Map",
        r"Podcasts",
        r"Careers",
        r"Help",
        r"Contact",
        r"News Tips",
        r"Got a confidential news tip\?",
        r"Get In Touch",
        r"CNBC Newsletters",
        r"Sign up for free newsletters",
        r"Get this delivered to your inbox",
        r"Advertise With Us",
        r"Please Contact Us",
        r"Privacy Policy",
        r"California Consumer Privacy Act",
        r"CA Notice",
        r"Terms of Service",
        r"© \d{4} CNBC LLC\. All Rights Reserved\.",
        r"A Division of NBCUniversal",
        r"Data is a real-time snapshot",
        r"Data is delayed at least 15 minutes\.",
        r"Global Business and Financial News, Stock Quotes, and Market Data and Analysis\.",
        r"Market Data Terms of Use and Disclaimers",
        r"Data also provided by",
        r"Reuters logo",
    ]

    for pattern in navigation_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove common HTML artifacts
    text = re.sub(r"\[.*?\]", "", text)  # Remove brackets

    # Clean up line breaks and spacing
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_metadata(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    """Extract all metadata from the article."""
    return {
        "title": _extract_title(soup),
        "author": _extract_author(soup),
        "publish_date": _extract_date(soup),
        "source": _extract_source(url),
    }


async def _fetch_html(url: str, ctx: ScraperContext) -> str:
    """Fetch HTML content with fallback to browser if needed."""

    # Try HTTP first
    try:
        # httpx 0.28 uses the singular ``proxy`` keyword.
        client_kwargs = {"timeout": ctx.timeout}
        if ctx.proxy:
            client_kwargs["proxy"] = ctx.proxy

        async with httpx.AsyncClient(**client_kwargs) as client:
            headers = ctx.headers.copy()
            headers.setdefault(
                "User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            headers.setdefault("Accept-Language", "en-US,en;q=0.9")

            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            html = resp.text

            # Detect common CDN block pages – they often exceed 1 kB but have no real article.
            _block_markers = [
                "Access Denied",  # Akamai / CloudFront
                "Captcha",  # generic captcha page
                "are you a robot",  # Cloudflare / Bloomberg
                "Request blocked",  # generic block
            ]

            blocked = any(m.lower() in html.lower() for m in _block_markers)

            if len(html) > 1000 and not blocked:
                if ctx.debug:
                    logger.info("http_success", url=url, length=len(html))
                return html

            # Otherwise treat as failure so we can fall back to browser.
            if ctx.debug and blocked:
                logger.info("http_blocked", url=url)
    except Exception as e:
        if ctx.debug:
            logger.warning("http_failed", url=url, error=str(e))

    # Browser fallback if enabled --------------------------------------------------
    if ctx.use_browser:
        # First try with the configured browser_type (Playwright or Selenium)
        try:
            html = await br.fetch_html("_article", lambda _t: url, ctx)
            if html and len(html) > 1000:
                if ctx.debug:
                    logger.info(
                        "browser_success", url=url, length=len(html), engine=ctx.browser_type
                    )
                return html
        except Exception as e:
            if ctx.debug:
                logger.warning("browser_failed", url=url, error=str(e), engine=ctx.browser_type)

        # Extra fallback: if initial attempt used Playwright, try Selenium once ----
        if ctx.browser_type.startswith("playwright") and br._SEL_AVAILABLE:
            ctx_sel = ScraperContext(
                headers=ctx.headers,
                timeout=ctx.timeout,
                retries=ctx.retries,
                user_agents=ctx.user_agents,
                proxy=ctx.proxy,
                use_browser=True,
                debug=ctx.debug,
                browser_type="selenium",
            )
            try:
                html = await br.fetch_html("_article", lambda _t: url, ctx_sel)
                if html and len(html) > 1000:
                    if ctx.debug:
                        logger.info("browser_success", url=url, length=len(html), engine="selenium")
                    return html
            except Exception as e:
                if ctx.debug:
                    logger.warning("browser_failed", url=url, error=str(e), engine="selenium")

    return ""


async def extract_article_content(url: str, ctx: ScraperContext | None = None) -> dict[str, Any]:
    """Extract clean article content from any URL.

    Args:
        url: The URL to extract content from
        ctx: ScraperContext for configuration

    Returns:
        Dictionary containing:
        - title: Article title
        - content: Main article text
        - summary: First paragraph or excerpt
        - publish_date: Publication date (YYYY-MM-DD)
        - author: Article author
        - source: Source name (e.g., "CNBC", "BLOOMBERG")
        - url: Original URL
    """

    # Default: enable browser fallback because many publishers block plain HTTP.
    if ctx is None:
        ctx = ScraperContext(use_browser=True, browser_type="playwright_stealth")

    # Fetch HTML
    html = await _fetch_html(url, ctx)
    if not html:
        return {
            "title": None,
            "content": "",
            "summary": "",
            "publish_date": None,
            "author": None,
            "source": _extract_source(url),
            "url": url,
            "error": "Failed to fetch content",
        }

    # Parse HTML
    soup = BeautifulSoup(html, "html.parser")

    # Extract metadata
    metadata = extract_metadata(soup, url)

    # Extract main content
    raw_content = _extract_main_content(soup)
    content = clean_text(raw_content)

    # Create summary (first paragraph or first 200 chars)
    summary = ""
    if content:
        paragraphs = content.split(". ")
        if paragraphs:
            summary = paragraphs[0][:200] + "..." if len(paragraphs[0]) > 200 else paragraphs[0]

    return {
        "title": metadata["title"],
        "content": content,
        "summary": summary,
        "publish_date": metadata["publish_date"],
        "author": metadata["author"],
        "source": metadata["source"],
        "url": url,
    }
