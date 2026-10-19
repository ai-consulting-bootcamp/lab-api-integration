import requests
from config import Config


class NewsAPI:
    """Fetch news articles from NewsAPI."""

    BASE_URL = "https://newsapi.org/v2/top-headlines"

    def __init__(self):
        self.config = Config()

    def get_articles(self, category="technology", limit=3):
        """Fetch news articles from a selected category."""

        if not self.config.news_api_key:
            raise ValueError("NEWS_API_KEY is missing.")

        # Define request parameters
        params = {
            "country": "us",
            "category": category,
            "pageSize": limit
        }

        # Authenticate using API key
        headers = {
            "X-Api-Key": self.config.news_api_key
        }

        # Send API request
        response = requests.get(
            self.BASE_URL,
            params=params,
            headers=headers,
            timeout=self.config.timeout
        )

        response.raise_for_status()

        # Convert JSON response to Python dictionary
        data = response.json()

        if data.get("status") != "ok":
            raise RuntimeError(data.get("message", "Unknown API error"))

        return data.get("articles", [])


if __name__ == "__main__":
    news_api = NewsAPI()

    try:
        articles = news_api.get_articles()

        print(f"Fetched {len(articles)} technology news articles.")

        for index, article in enumerate(articles, start=1):
            print(f"\nArticle {index}:")
            print(f"Title: {article.get('title')}")
            print(f"Source: {article.get('source', {}).get('name')}")
            print(f"URL: {article.get('url')}")

    except (requests.exceptions.RequestException, ValueError, RuntimeError) as e:
        print(f"Error fetching news: {e}")