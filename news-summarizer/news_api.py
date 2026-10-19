"""Fetch and display technology news from NewsAPI.org.

The API key is read from ``NEWS_API_KEY`` (or a local ``.env`` file).  The
module is intentionally small so the returned articles can be passed directly
to the summarizer in later steps of the lab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from config import get_config


NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
DEFAULT_ARTICLE_COUNT = 3


@dataclass(frozen=True)
class NewsArticle:
    """A normalized news article returned by NewsAPI."""

    title: str
    source: str
    description: str
    url: str
    published_at: str


class NewsAPIError(RuntimeError):
    """Raised when NewsAPI cannot return a valid article response."""


def _article_from_payload(payload: dict[str, Any]) -> NewsArticle:
    """Convert one NewsAPI article payload into a :class:`NewsArticle`."""

    source = payload.get("source") or {}
    return NewsArticle(
        title=payload.get("title") or "Untitled",
        source=source.get("name") or "Unknown source",
        description=payload.get("description") or "No description available.",
        url=payload.get("url") or "",
        published_at=payload.get("publishedAt") or "Unknown publication date",
    )


def fetch_tech_news(count: int = DEFAULT_ARTICLE_COUNT) -> list[NewsArticle]:
    """Fetch up to ``count`` current technology headlines.

    Args:
        count: Number of articles to request.  It must be positive.

    Returns:
        A list of normalized :class:`NewsArticle` objects.

    Raises:
        ValueError: If ``count`` is not positive.
        NewsAPIError: If the API key is missing or the request fails.
    """

    if count < 1:
        raise ValueError("count must be greater than zero")

    config = get_config()
    api_key = config.news_api_key
    if not api_key:
        raise NewsAPIError(
            "NEWS_API_KEY is not set. Add it to the environment or news-summarizer/.env."
        )

    try:
        response = requests.get(
            NEWS_API_URL,
            params={
                "apiKey": api_key,
                "country": "us",
                "category": "technology",
                "pageSize": count,
            },
            timeout=config.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise NewsAPIError(f"Could not fetch technology news: {exc}") from exc
    except ValueError as exc:
        raise NewsAPIError("NewsAPI returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise NewsAPIError("NewsAPI returned an unexpected response format.")

    if data.get("status") != "ok":
        message = data.get("message", "NewsAPI returned an unsuccessful response.")
        raise NewsAPIError(message)

    raw_articles = data.get("articles")
    if not isinstance(raw_articles, list):
        raise NewsAPIError("NewsAPI response did not contain an articles list.")

    return [_article_from_payload(article) for article in raw_articles[:count]]


def display_articles(articles: list[NewsArticle]) -> None:
    """Print articles in a readable format for the command line."""

    if not articles:
        print("No technology news articles were found.")
        return

    for index, article in enumerate(articles, start=1):
        print(f"\n{index}. {article.title}")
        print(f"   Source: {article.source}")
        print(f"   Published: {article.published_at}")
        print(f"   {article.description}")
        print(f"   Read more: {article.url}")


def main() -> None:
    """Fetch and display the three required technology articles."""

    try:
        articles = fetch_tech_news(DEFAULT_ARTICLE_COUNT)
        display_articles(articles)
    except NewsAPIError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
