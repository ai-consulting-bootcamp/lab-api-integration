"""
news_api.py - External data source 
Real version of the training's fetch_weather_data() mock: fetches recent articles
from AskNews (asknews.app) to enrich the LLM prompts. The API key is read from
NEWS_API_KEY in .env.
"""

import os
from typing import Any, Dict, List, Optional

from asknews_sdk import AskNewsSDK
from asknews_sdk.errors import APIError

from config import Config
from llm_providers import RateLimiter

config = Config()

# Map the lab's categories to AskNews categories
CATEGORY_MAP = {
    "business": "Business",
    "entertainment": "Entertainment",
    "general": "All",
    "health": "Health",
    "science": "Science",
    "sports": "Sports",
    "technology": "Technology",
}

# AskNews rate limit (lab requirement: "Respects rate limits"); free plans are limited
news_rate_limiter = RateLimiter(requests_per_minute=10)


def fetch_news(category: str = "technology", page_size: int = 3,
               api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch recent articles for a category from AskNews.

    Args:
        category: business, entertainment, general, health, science, sports or technology
        page_size: Number of articles to fetch
        api_key: AskNews API key (read from NEWS_API_KEY in .env if not given)

    Returns:
        List of article dictionaries (empty list if the request fails)
    """
    api_key = api_key or os.getenv("NEWS_API_KEY")
    print(f"📰 Fetching {page_size} {category} articles from AskNews...")

    news_rate_limiter.wait()
    try:
        ask = AskNewsSDK(api_key=api_key, scopes={"news"}, timeout=config.timeout)
        response = ask.news.search_news(
            query=f"latest {category} news",
            n_articles=page_size,
            return_type="dicts",
            method="kw",
            categories=[CATEGORY_MAP.get(category, "All")],
        )
    except APIError as e:
        masked = f"{api_key[:4]}...{api_key[-4:]} (length {len(api_key)})" if api_key else "NOT SET"
        print(f"❌ AskNews error {e.code}: {e.detail}")
        print(f"   Key sent: {masked}")
        return []
    except Exception as e:
        print(f"❌ AskNews request failed: {type(e).__name__}: {e}")
        return []

    # Keep only the fields the summarizer uses 
    articles = [
        {
            "title": item.eng_title or item.title,
            "source": item.domain_url or item.source_id,
            "description": item.summary or "",
            "content": " ".join(item.key_points or []),
            "url": str(item.article_url),
            "published_at": item.pub_date.isoformat() if item.pub_date else None
        }
        for item in (response.as_dicts or [])
        if item.title
    ]

    print(f"   Found {len(articles)} articles")
    return articles


if __name__ == "__main__":
    # Checkpoint 2: fetch and display 3 tech news articles
    config.validate()
    articles = fetch_news(category="technology", page_size=3)

    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Source: {article['source']} | {article['published_at']}")
        print(f"   {article['url']}")
