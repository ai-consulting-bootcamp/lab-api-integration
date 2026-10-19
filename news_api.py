import requests
from config import get_config

def fetch_latest_news(limit=3):
    """Fetches and cleans the latest technology news articles using NewsAPI."""
    config = get_config()
    print(repr(config.NEWS_API_KEY))
    url = "https://newsapi.org/v2/top-headlines"
    
    # We use the parameters to filter the results down to just english tech news
    params = {
        "category": "technology",
        "language": "en",
        "pageSize": limit,
    }
    # Keep the API key out of the URL, where it can be exposed in logs/errors.
    headers = {"X-Api-Key": config.NEWS_API_KEY}
    
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )

        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            print("News API returned an unexpected non-JSON response.")
            return []
        
        if response.status_code != 200 or data.get("status") != "ok":
            code = data.get("code", f"http_{response.status_code}")
            message = data.get("message", response.reason)
            print(f"News API error ({code}): {message}")
            return []
            
        articles = []
        for item in data.get("articles", []):
            # Clean the data: only keep articles that actually have text content
            if item.get("title") and item.get("content"):
                articles.append({
                    "title": item["title"],
                    "content": item["content"],
                    "source": item["source"]["name"]
                })
        return articles
        
    except requests.exceptions.RequestException as e:
        print(f"Network error while fetching news: {e}")
        return []

# Checkpoint 2: Run this file directly to test the News API integration
if __name__ == "__main__":
    print("Fetching news articles...")
    articles = fetch_latest_news()
    
    if articles:
        print(f"✅ Checkpoint 2 passed! Successfully fetched {len(articles)} articles:\n")
        for i, art in enumerate(articles, 1):
            print(f"{i}. {art['title']}")
            print(f"   Source: {art['source']}\n")
    else:
        print("❌ Failed to fetch articles. Check your API key and network connection.")
