import pytest

from web_search_sdk.scrapers.duckduckgo_web import _parse_html

HTML_FIXTURE = """
<html><body>
  <div class="result">
    <a class="result__a" href="http://example.com">OpenAI Stock Analysis</a>
    <div class="result__snippet">OpenAI stock surges on new product release</div>
  </div>
  <div class="result">
    <a class="result__a" href="http://foo.com">Investing in AI companies</a>
    <a class="result__snippet">The AI sector including OpenAI shows potential</a>
  </div>
</body></html>
"""


@pytest.mark.parametrize("top_n,expected", [(5, {"openai", "stock"})])
def test_parse_html_tokens(top_n, expected):
    tokens = _parse_html(HTML_FIXTURE, top_n=top_n)
    assert expected.issubset(set(tokens)), f"Expected tokens {expected} in {tokens}"
