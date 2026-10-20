
import requests
from config import get_config


class NewsAPI:
    """Fetch news articles from NewsAPI.org."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self):
        self.config = get_config()

    def get_top_headlines(self, category="technology", country="us", page_size=3):
        """Fetch top headlines for a category."""
        params = {
            "apiKey": self.config.news_api_key,
            "category": category,
            "country": country,
            "pageSize": page_size,
        }

        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.config.request_timeout,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("articles", [])

        except requests.exceptions.RequestException as error:
            print(f"News API error: {error}")
            return []


if __name__ == "__main__":
    news_api = NewsAPI()
    articles = news_api.get_top_headlines()

    print(f"Fetched {len(articles)} articles:\n")

    for index, article in enumerate(articles, start=1):
        print(f"{index}. {article.get('title', 'No title')}")
        print(f"   Source: {article.get('source', {}).get('name', 'Unknown')}")
        print(f"   URL: {article.get('url', 'N/A')}\n")
