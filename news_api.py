
import requests
from config import NEWS_API_KEY, REQUEST_TIMEOUT


def fetch_news(category="technology", country="us", limit=3):
    """Fetch news articles from NewsAPI."""

    url = "https://newsapi.org/v2/top-headlines"

    params = {
        "apiKey": NEWS_API_KEY,
        "category": category,
        "country": country,
        "pageSize": limit
    }

    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if data.get("status") != "ok":
        raise ValueError("NewsAPI returned an error")

    return data.get("articles", [])


if __name__ == "__main__":
    articles = fetch_news()

    print(f"Fetched {len(articles)} articles\n")

    for index, article in enumerate(articles, start=1):
        print(f"{index}. {article.get('title')}")
        print(f"Source: {article.get('source', {}).get('name')}")
        print(f"URL: {article.get('url')}")
        print()
