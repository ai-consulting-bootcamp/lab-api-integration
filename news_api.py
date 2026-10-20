"""NewsAPI client for top headlines."""

from __future__ import annotations

from dataclasses import dataclass
from random import random
from time import sleep
from typing import Any, Callable, Mapping

import requests
from requests import Response, Session
from requests.exceptions import RequestException, Timeout

from config import Config, ConfigError, get_config

_NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
_ALLOWED_COUNTRIES = {"us"}
_ALLOWED_CATEGORIES = {"technology"}
_ALLOWED_PAGE_SIZE_RANGE = range(1, 101)
_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class NewsArticle:
    """Normalized article data with the original payload preserved."""

    source: dict[str, Any]
    author: str | None
    title: str
    description: str | None
    url: str
    url_to_image: str | None
    published_at: str | None
    content: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NewsFetchDiagnostics:
    """Safe counters for a NewsAPI fetch."""

    requested_page_size: int
    received_count: int
    kept_count: int
    discarded_count: int
    discard_reasons: dict[str, int]


class NewsAPIError(RuntimeError):
    """Raised when NewsAPI returns a failure or invalid payload."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        newsapi_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.newsapi_code = newsapi_code

    def __str__(self) -> str:
        parts: list[str] = [super().__str__()]
        if self.http_status is not None:
            parts.append(f"HTTP {self.http_status}")
        if self.newsapi_code:
            parts.append(f"NewsAPI code={self.newsapi_code}")
        return " | ".join(parts)


class NewsAPIClient:
    """Client for the NewsAPI top-headlines endpoint."""

    def __init__(
        self,
        config: Config,
        *,
        session: Session | None = None,
        sleep_fn: Callable[[float], None] = sleep,
        random_fn: Callable[[], float] = random,
        base_url: str = _NEWS_API_URL,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._sleep = sleep_fn
        self._random = random_fn
        self._base_url = base_url

    def fetch_top_headlines(
        self,
        *,
        category: str = "technology",
        country: str = "us",
        page_size: int = 3,
        page: int = 1,
        diagnostics_hook: Callable[[NewsFetchDiagnostics], None] | None = None,
    ) -> list[NewsArticle]:
        """Fetch and normalize top headlines."""

        self._validate_params(category=category, country=country, page_size=page_size, page=page)

        params = {
            "category": category,
            "country": country,
            "pageSize": page_size,
            "page": page,
        }
        headers = {"X-Api-Key": self._config.news_api_key}

        attempt = 0
        while True:
            try:
                response = self._session.get(
                    self._base_url,
                    params=params,
                    headers=headers,
                    timeout=self._config.request_timeout,
                )
            except Timeout as exc:
                if attempt >= self._config.max_retries:
                    raise NewsAPIError(
                        "NewsAPI request timed out after the configured retries.",
                    ) from exc
                self._backoff_sleep(attempt, None)
                attempt += 1
                continue
            except RequestException as exc:
                if attempt >= self._config.max_retries:
                    raise NewsAPIError(
                        "NewsAPI request failed due to a network error after the configured retries.",
                    ) from exc
                self._backoff_sleep(attempt, None)
                attempt += 1
                continue

            if response.status_code == 200:
                payload = self._parse_json(response)
                articles, diagnostics = self._parse_articles(payload, requested_page_size=page_size)
                if diagnostics_hook is not None:
                    diagnostics_hook(diagnostics)
                return articles

            error_payload = self._safe_error_payload(response)
            newsapi_code = error_payload.get("code") if isinstance(error_payload, dict) else None
            error_message = error_payload.get("message") if isinstance(error_payload, dict) else None

            if response.status_code in {401, 403}:
                raise self._authorization_error(response.status_code, newsapi_code, error_message)

            if response.status_code not in _RETRYABLE_HTTP_STATUSES or attempt >= self._config.max_retries:
                raise self._http_error(response.status_code, newsapi_code, error_message)

            self._backoff_sleep(attempt, response)
            attempt += 1

    def _validate_params(self, *, category: str, country: str, page_size: int, page: int) -> None:
        """Validate request parameters before performing an HTTP call."""

        if category not in _ALLOWED_CATEGORIES:
            raise ValueError("category must be technology")
        if country not in _ALLOWED_COUNTRIES:
            raise ValueError("country must be us")
        if page_size not in _ALLOWED_PAGE_SIZE_RANGE:
            raise ValueError("page_size must be between 1 and 100")
        if page < 1:
            raise ValueError("page must be greater than or equal to 1")

    def _parse_json(self, response: Response) -> Mapping[str, Any]:
        """Parse a JSON response and validate the top-level shape."""

        try:
            payload = response.json()
        except ValueError as exc:
            raise NewsAPIError(
                "NewsAPI returned invalid JSON.",
                http_status=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise NewsAPIError(
                "NewsAPI returned a JSON payload with an invalid top-level structure.",
                http_status=response.status_code,
            )
        return payload

    def _parse_articles(
        self,
        payload: Mapping[str, Any],
        *,
        requested_page_size: int,
    ) -> tuple[list[NewsArticle], NewsFetchDiagnostics]:
        """Validate the NewsAPI payload and return usable articles."""

        status = payload.get("status")
        if status != "ok":
            code = payload.get("code") if isinstance(payload.get("code"), str) else None
            message = payload.get("message") if isinstance(payload.get("message"), str) else None
            raise NewsAPIError(
                self._format_api_error_message(),
                newsapi_code=code,
            )

        articles = payload.get("articles")
        if not isinstance(articles, list):
            raise NewsAPIError("NewsAPI returned an invalid articles collection.")

        parsed_articles: list[NewsArticle] = []
        discard_reasons: dict[str, int] = {}
        for article in articles:
            if not isinstance(article, dict):
                _increment(discard_reasons, "non_object")
                continue
            normalized = self._normalize_article(article, discard_reasons=discard_reasons)
            if normalized is not None:
                parsed_articles.append(normalized)
        diagnostics = NewsFetchDiagnostics(
            requested_page_size=requested_page_size,
            received_count=len(articles),
            kept_count=len(parsed_articles),
            discarded_count=max(0, len(articles) - len(parsed_articles)),
            discard_reasons=discard_reasons,
        )
        return parsed_articles, diagnostics

    def _normalize_article(
        self,
        article: Mapping[str, Any],
        *,
        discard_reasons: dict[str, int] | None = None,
    ) -> NewsArticle | None:
        """Return a normalized article or ``None`` when the title is unusable."""

        title = self._clean_text(article.get("title"))
        if title is None:
            if discard_reasons is not None:
                _increment(discard_reasons, "title_unusable")
            return None

        source = article.get("source")
        if isinstance(source, dict):
            source_payload = dict(source)
        else:
            source_payload = {}

        return NewsArticle(
            source=source_payload,
            author=self._optional_text(article.get("author")),
            title=title,
            description=self._optional_text(article.get("description")),
            url=self._clean_url(article.get("url"), discard_reasons=discard_reasons),
            url_to_image=self._optional_text(article.get("urlToImage")),
            published_at=self._optional_text(article.get("publishedAt")),
            content=self._optional_text(article.get("content")),
            raw=dict(article),
        )

    def _clean_url(self, value: Any, *, discard_reasons: dict[str, int] | None = None) -> str:
        """Return a usable URL or raise a safe error."""

        url = self._clean_text(value)
        if url is None:
            if discard_reasons is not None:
                _increment(discard_reasons, "missing_url")
            raise NewsAPIError("NewsAPI article is missing a usable url field.")
        return url

    def _optional_text(self, value: Any) -> str | None:
        """Normalize optional article text fields."""

        if value is None:
            return None
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text or None

    def _clean_text(self, value: Any) -> str | None:
        """Normalize text fields and filter out blanks and removed titles."""

        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        lowered = text.casefold()
        if lowered in {"[removed]", "removed"}:
            return None
        return text

    def _safe_error_payload(self, response: Response) -> Mapping[str, Any] | None:
        """Parse an error body without surfacing raw response text."""

        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None

    def _authorization_error(
        self,
        http_status: int,
        newsapi_code: str | None,
        message: str | None,
    ) -> NewsAPIError:
        """Build a safe 401/403 error with remediation guidance."""

        safe_message = self._format_api_error_message()
        if newsapi_code == "apiKeyInvalid" or http_status == 401:
            safe_message = (
                "NewsAPI authorization failed. Save your .env file, verify the local API key, "
                "confirm the account email if required, and restart the program."
            )
        return NewsAPIError(safe_message, http_status=http_status, newsapi_code=newsapi_code)

    def _http_error(
        self,
        http_status: int,
        newsapi_code: str | None,
        message: str | None,
    ) -> NewsAPIError:
        """Build a safe HTTP error message."""

        return NewsAPIError(
            self._format_api_error_message(),
            http_status=http_status,
            newsapi_code=newsapi_code,
        )

    def _format_api_error_message(self) -> str:
        """Return a safe generic NewsAPI error message."""

        return "NewsAPI request failed with an error response."

    def _backoff_sleep(self, attempt: int, response: Response | None) -> None:
        """Sleep with exponential backoff, jitter, and an optional Retry-After cap."""

        delay = min(2 ** attempt, 30)
        jitter = self._random() * 0.5
        retry_after = self._retry_after_delay(response)
        if retry_after is not None:
            delay = min(delay + jitter, retry_after)
        else:
            delay = delay + jitter
        self._sleep(max(0.0, delay))

    def _retry_after_delay(self, response: Response | None) -> float | None:
        """Parse Retry-After with a conservative cap."""

        if response is None:
            return None
        header_value = response.headers.get("Retry-After")
        if not header_value:
            return None
        try:
            retry_after = float(header_value)
        except (TypeError, ValueError):
            return None
        if retry_after <= 0:
            return None
        return min(retry_after, self._config.request_timeout)


def fetch_top_headlines(
    *,
    config: Config | None = None,
    session: Session | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    random_fn: Callable[[], float] = random,
    category: str = "technology",
    country: str = "us",
    page_size: int = 3,
    page: int = 1,
    diagnostics_hook: Callable[[NewsFetchDiagnostics], None] | None = None,
) -> list[NewsArticle]:
    """Fetch top headlines using the configured NewsAPI credentials."""

    active_config = config or get_config()
    client = NewsAPIClient(
        active_config,
        session=session,
        sleep_fn=sleep_fn,
        random_fn=random_fn,
    )
    return client.fetch_top_headlines(
        category=category,
        country=country,
        page_size=page_size,
        page=page,
        diagnostics_hook=diagnostics_hook,
    )


def _increment(counts: dict[str, int], key: str) -> None:
    """Increase a safe counter by one."""

    counts[key] = counts.get(key, 0) + 1


def _main() -> int:
    """Run a small command-line smoke test."""

    try:
        articles = fetch_top_headlines()
    except (ConfigError, NewsAPIError, ValueError) as exc:
        print(str(exc))
        return 1

    print(f"usable articles: {len(articles)}")
    for index, article in enumerate(articles, start=1):
        source_name = article.source.get("name") if isinstance(article.source, dict) else None
        print(f"{index}. {article.title}")
        print(f"   source: {source_name or 'unknown'}")
        print(f"   url: {article.url}")
    if len(articles) < 3:
        print(f"Checkpoint 2 is not fully passed yet: received {len(articles)} usable articles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
