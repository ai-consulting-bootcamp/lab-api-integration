# die abruffunktion:

import requests

from config import NEWS_API_KEY, ARTICLE_COUNT, REQUEST_TIMEOUT


def fetch_articles(topic):
    response = requests.get(
        "https://newsapi.org/v2/everything",
        headers={"X-Api-Key": NEWS_API_KEY},
        params={
            "q": topic,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": ARTICLE_COUNT,
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()
    data = response.json()

    return data["articles"]


# test: 
if __name__ == "__main__":
    articles = fetch_articles('"artificial intelligence"')

    for article in articles:
        print("Titel:", article["title"])
        print("Quelle:", article["source"]["name"])
        print("Autor:", article["author"])
        print("Veröffentlicht:", article["publishedAt"])
        print("Beschreibung:", article["description"])
        print("-" * 60)