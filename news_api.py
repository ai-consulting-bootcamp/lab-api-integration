"""Small client for retrieving news articles from NewsAPI."""

from typing import Any

import requests

from config import Config, get_config


class NewsAPIError(RuntimeError):
    """Raised when NewsAPI cannot return articles."""


class NewsAPIClient:
    """Fetch and normalize top headlines."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self, config: Config | None = None, session: requests.Session | None = None):
        self.config = config or get_config()
        self.session = session or requests.Session()

    def top_headlines(self, category: str = "technology", page_size: int = 3) -> list[dict[str, Any]]:
        """Return a small, predictable article shape for the workflow."""
        if not self.config.news_api_key:
            raise NewsAPIError("NEWS_API_KEY is not configured")
        try:
            response = self.session.get(
                self.BASE_URL,
                params={
                    "apiKey": self.config.news_api_key,
                    "country": "us",
                    "category": category,
                    "pageSize": page_size,
                },
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise NewsAPIError(f"NewsAPI request failed: {exc}") from exc

        if payload.get("status") != "ok":
            raise NewsAPIError(payload.get("message", "NewsAPI returned an error"))
        return [
            {
                "title": article.get("title", "Untitled"),
                "description": article.get("description") or "",
                "content": article.get("content") or article.get("description") or "",
                "url": article.get("url", ""),
                "source": (article.get("source") or {}).get("name", "Unknown"),
            }
            for article in payload.get("articles", [])
        ]


if __name__ == "__main__":
    articles = NewsAPIClient().top_headlines()
    for article in articles:
        print(f"- {article['title']}")
