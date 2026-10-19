"""Fetch and display technology headlines from NewsAPI."""

import sys
from typing import Any

import requests

from config import NEWS_API_KEY, REQUEST_TIMEOUT


NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


def fetch_tech_news(limit: int = 3) -> list[dict[str, Any]]:
    """Fetch up to ``limit`` US technology headlines from NewsAPI."""
    if not NEWS_API_KEY:
        raise RuntimeError(
            "NEWS_API_KEY is missing. Add it to the .env file and try again."
        )
    if limit < 1:
        raise ValueError("limit must be at least 1")

    try:
        response = requests.get(
            NEWS_API_URL,
            params={
                "apiKey": NEWS_API_KEY,
                "country": "us",
                "category": "technology",
                "pageSize": limit,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as error:
        raise RuntimeError("The NewsAPI request timed out.") from error
    except requests.RequestException as error:
        raise RuntimeError("Could not connect to NewsAPI.") from error

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as error:
        if not response.ok:
            raise RuntimeError(
                f"NewsAPI returned HTTP {response.status_code} with a non-JSON "
                "error response."
            ) from error
        raise RuntimeError("NewsAPI returned an invalid JSON response.") from error

    if not isinstance(payload, dict):
        if not response.ok:
            raise RuntimeError(f"NewsAPI returned HTTP {response.status_code}.")
        raise RuntimeError("NewsAPI returned an unexpected response format.")

    if not response.ok:
        code = payload.get("code")
        message = payload.get("message")
        details = ": " + str(message) if message else ""
        error_code = f" ({code})" if code else ""
        raise RuntimeError(
            f"NewsAPI returned HTTP {response.status_code}{error_code}{details}"
        )

    if payload.get("status") != "ok":
        code = payload.get("code")
        message = payload.get("message", "Unknown NewsAPI error.")
        error_code = f" ({code})" if code else ""
        raise RuntimeError(f"NewsAPI error{error_code}: {message}")

    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise RuntimeError("NewsAPI response did not contain an article list.")

    return articles[:limit]


def display_articles(articles: list[dict[str, Any]]) -> None:
    """Print article titles, sources, publication dates, and URLs."""
    if not articles:
        print("No technology articles were returned.")
        return

    for number, article in enumerate(articles, start=1):
        source = article.get("source") or {}
        print(f"{number}. {article.get('title') or 'Untitled'}")
        print(f"   Source: {source.get('name') or 'Unknown'}")
        print(f"   Published: {article.get('publishedAt') or 'Unknown'}")
        print(f"   URL: {article.get('url') or 'Unavailable'}")


if __name__ == "__main__":
    try:
        display_articles(fetch_tech_news())
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)