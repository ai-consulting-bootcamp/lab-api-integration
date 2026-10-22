"""News API client: fetches top headlines from newsapi.org."""

import time

import requests

from config import get_config

BASE_URL = "https://newsapi.org/v2"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class NewsAPIError(Exception):
    """Raised when a News API request cannot be completed successfully."""


class NewsAPIClient:
    """Retrieve and filter headlines from the News API."""

    def __init__(self):
        config = get_config()
        self.max_retries = config.max_retries
        self.timeout = config.request_timeout
        # Keep the API key out of URL query parameters.
        self.headers = {"X-Api-Key": config.news_api_key}

    def get_top_headlines(self, category="technology", country="us", page_size=5):
        """Return articles with valid titles, excluding removed stories."""
        params = {
            "category": category,
            "country": country,
            "pageSize": page_size,
        }
        data = self._get("/top-headlines", params)

        return [
            article
            for article in data.get("articles", [])
            if article.get("title") and article["title"] != "[Removed]"
        ]

    def _get(self, path, params):
        """Retry temporary network or server failures with exponential backoff."""
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    f"{BASE_URL}{path}",
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = f"network problem: {type(error).__name__}"
            else:
                if response.status_code not in RETRYABLE_STATUS:
                    return self._parse(response)
                last_error = f"HTTP {response.status_code}"

            if attempt < self.max_retries:
                # Back off between attempts: 1, 2, 4 seconds, etc.
                time.sleep(2 ** (attempt - 1))

        raise NewsAPIError(
            f"News API failed after {self.max_retries} attempts ({last_error})"
        )

    @staticmethod
    def _parse(response):
        """Validate the API response and return its JSON data."""
        try:
            data = response.json()
        except ValueError as error:
            raise NewsAPIError(
                f"News API sent invalid JSON (HTTP {response.status_code})"
            ) from error

        if response.status_code != 200 or data.get("status") != "ok":
            code = data.get("code", "unknown")
            message = data.get("message", "no message")
            raise NewsAPIError(f"News API error [{code}]: {message}")

        return data


def main():
    """Fetch and display a few technology headlines."""
    try:
        articles = NewsAPIClient().get_top_headlines(
            category="technology", page_size=3
        )
    except (ValueError, NewsAPIError) as error:
        print(f"❌ {error}")
        raise SystemExit(1) from error

    print(f"✅ Fetched {len(articles)} articles\n")
    for number, article in enumerate(articles, start=1):
        print(f"{number}. {article['title']}")
        print(f"   Source: {article['source']['name']}")
        print(f"   {article.get('description') or 'No description'}")
        print(f"   {article['url']}\n")


if __name__ == "__main__":
    main()
