"""Fetch top headlines from newsapi.org."""
import requests
from config import get_config

NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


def fetch_top_headlines(category="technology", country="us", page_size=3):
    """Return a list of articles as simple dictionaries."""
    config = get_config()
    params = {
        "category": category,
        "country": country,
        "pageSize": page_size,
        "apiKey": config.news_api_key,
    }

    try:
        response = requests.get(NEWS_API_URL, params=params,
                                timeout=config.request_timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"[news_api] No answer after {config.request_timeout}s. "
                           "Check your internet connection.")
    except requests.exceptions.HTTPError:
        raise RuntimeError(f"[news_api] HTTP {response.status_code}: {response.text[:200]}. "
                           "Check NEWS_API_KEY in .env.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"[news_api] {type(e).__name__}: {e}")

    data = response.json()
    articles = []
    for item in data.get("articles", []):
        if not item.get("title"):
            continue  # skip broken entries
        articles.append({
            "title": item["title"],
            "description": item.get("description") or "",
            "content": item.get("content") or "",
            "source": (item.get("source") or {}).get("name", "Unknown"),
            "url": item.get("url", ""),
            "published_at": item.get("publishedAt", ""),
        })
    return articles


if __name__ == "__main__":
    articles = fetch_top_headlines(page_size=3)
    print(f"✅ Fetched {len(articles)} articles\n")
    for i, a in enumerate(articles, 1):
        print(f"{i}. {a['title']}")
        print(f"   Source: {a['source']} | {a['published_at']}")
        print(f"   {a['description'][:120]}\n")