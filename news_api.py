"""News API module: fetches and cleans articles from newsapi.org."""
import requests

from config import Config


class NewsAPI:
    """Small client for the News API top-headlines endpoint."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key=None, timeout=None):
        """Use keys/timeouts from Config unless overridden (useful in tests)."""
        self.api_key = api_key or Config.NEWS_API_KEY
        self.timeout = timeout or Config.REQUEST_TIMEOUT

    def fetch_top_headlines(self, category="technology", country="us",
                            max_articles=5):
        """Return a list of cleaned article dicts, or [] if anything fails."""
        params = {
            "category": category,
            "country": country,
            "pageSize": max_articles,
        }
        # Key goes in a header, not the URL, so it never shows up in logs
        headers = {"X-Api-Key": self.api_key}

        try:
            response = requests.get(
                f"{self.BASE_URL}/top-headlines",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as error:
            print(f"✗ Could not reach News API: {error}")
            return []

        if data.get("status") != "ok":
            print(f"✗ News API error: {data.get('message', 'unknown error')}")
            return []

        return [
            self._clean_article(article)
            for article in data.get("articles", [])
            if article.get("title") and article["title"] != "[Removed]"
        ]

    @staticmethod
    def _clean_article(article):
        """Keep only the fields we need, with safe defaults for missing ones."""
        return {
            "title": article.get("title", ""),
            "description": article.get("description") or "",
            "content": article.get("content") or "",
            "url": article.get("url", ""),
            "source": (article.get("source") or {}).get("name", "Unknown"),
            "published_at": article.get("publishedAt", ""),
        }


if __name__ == "__main__":
    news = NewsAPI()
    articles = news.fetch_top_headlines(max_articles=3)
    print(f"Fetched {len(articles)} articles")
    print()
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   {article['description'][:120]}...")
        print()