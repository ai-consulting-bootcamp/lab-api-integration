import os

import requests
from dotenv import load_dotenv


load_dotenv()


def fetch_tech_news():
    """Fetch three technology news articles."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise ValueError("NEWS_API_KEY is missing from the .env file")

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "us",
        "category": "technology",
        "pageSize": 3,
    }

    response = requests.get(
        url,
        params=params,
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("status") != "ok":
        message = data.get("message", "Unknown News API error")
        raise RuntimeError(f"News API error: {message}")

    articles = data.get("articles", [])
    if not articles:
        raise ValueError("No news articles were returned")

    return articles


if __name__ == "__main__":
    articles = fetch_tech_news()

    for article in articles:
        print(f"Title: {article.get('title', 'No title')}")
        print(f"Source: {article.get('source', {}).get('name', 'Unknown')}")
        print(f"URL: {article.get('url', 'No URL')}")
        print()