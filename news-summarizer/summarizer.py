"""Summarize technology news and analyze the sentiment of each summary."""

import asyncio
import logging
import sys
import time
from typing import Any

from config import DAILY_BUDGET
from llm_providers import CohereProvider, CostTracker, OpenAIProvider
from news_api import fetch_tech_news


logger = logging.getLogger(__name__)


class NewsSummarizer:
    """Summarize articles with OpenAI and analyze sentiment with Cohere."""

    def __init__(
        self,
        openai_provider: OpenAIProvider | None = None,
        cohere_provider: CohereProvider | None = None,
        cost_tracker: CostTracker | None = None,
        request_interval: float = 1.0,
    ) -> None:
        if request_interval < 0:
            raise ValueError("request_interval cannot be negative")

        self.cost_tracker = cost_tracker or CostTracker()
        self.openai_provider = openai_provider or OpenAIProvider(
            cost_tracker=self.cost_tracker
        )
        self.cohere_provider = cohere_provider or CohereProvider(
            cost_tracker=self.cost_tracker
        )
        self.request_interval = request_interval
        self._last_request_time: float | None = None
        self._async_request_lock = asyncio.Lock()
        self._async_last_request_time: float | None = None

    def _generate(
        self, provider: OpenAIProvider | CohereProvider, prompt: str
    ) -> str:
        if self.cost_tracker.total_cost >= DAILY_BUDGET:
            raise RuntimeError(
                f"Daily budget of ${DAILY_BUDGET:.2f} has been reached."
            )

        if self._last_request_time is not None:
            elapsed = time.monotonic() - self._last_request_time
            wait = self.request_interval - elapsed
            if wait > 0:
                time.sleep(wait)

        self._last_request_time = time.monotonic()
        return provider.generate(prompt)

    def _generate_with_fallback(
        self,
        primary: OpenAIProvider | CohereProvider,
        fallback: OpenAIProvider | CohereProvider,
        prompt: str,
    ) -> str:
        try:
            return self._generate(primary, prompt)
        except Exception as primary_error:
            logger.warning(
                "%s request failed; retrying with %s: %s",
                type(primary).__name__,
                type(fallback).__name__,
                primary_error,
            )
            try:
                return self._generate(fallback, prompt)
            except Exception as fallback_error:
                raise RuntimeError(
                    "Both LLM providers failed. "
                    f"Primary error: {primary_error}; "
                    f"fallback error: {fallback_error}"
                ) from fallback_error

    @staticmethod
    def _article_text(article: dict[str, Any]) -> str:
        parts = []
        for field in ("title", "description", "content"):
            value = article.get(field)
            if value is not None:
                text = str(value).strip()
                if text:
                    parts.append(text)
        if not parts:
            raise ValueError("Article must include a title, description, or content.")
        return "\n".join(parts)

    def summarize_article(self, article: dict[str, Any]) -> str:
        """Return a concise summary of an article, with provider fallback."""
        prompt = (
            "Summarize the following news article in 2-3 concise sentences. "
            "Preserve its key facts and do not add information.\n\n"
            f"{self._article_text(article)}"
        )
        return self._generate_with_fallback(
            self.openai_provider, self.cohere_provider, prompt
        )

    def analyze_sentiment(self, summary: str) -> str:
        """Analyze a summary's sentiment, with provider fallback."""
        if not summary.strip():
            raise ValueError("summary cannot be empty")
        prompt = (
            "Analyze the sentiment of the following news summary. "
            "Label it Positive, Negative, or Neutral and briefly explain why.\n\n"
            f"{summary}"
        )
        return self._generate_with_fallback(
            self.cohere_provider, self.openai_provider, prompt
        )

    def process_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """Return an article augmented with its summary and sentiment."""
        summary = self.summarize_article(article)
        result = dict(article)
        result["summary"] = summary
        result["sentiment"] = self.analyze_sentiment(summary)
        return result

    def process_articles(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process articles sequentially to respect the provider request interval."""
        return [self.process_article(article) for article in articles]

    async def _async_generate(
        self, provider: OpenAIProvider | CohereProvider, prompt: str
    ) -> str:
        if self.cost_tracker.total_cost >= DAILY_BUDGET:
            raise RuntimeError(
                f"Daily budget of ${DAILY_BUDGET:.2f} has been reached."
            )

        async with self._async_request_lock:
            if self._async_last_request_time is not None:
                elapsed = time.monotonic() - self._async_last_request_time
                wait = self.request_interval - elapsed
                if wait > 0:
                    await asyncio.sleep(wait)
            self._async_last_request_time = time.monotonic()

        return await asyncio.to_thread(provider.generate, prompt)

    async def _async_generate_with_fallback(
        self,
        primary: OpenAIProvider | CohereProvider,
        fallback: OpenAIProvider | CohereProvider,
        prompt: str,
    ) -> str:
        try:
            return await self._async_generate(primary, prompt)
        except Exception as primary_error:
            logger.warning(
                "%s request failed; retrying with %s: %s",
                type(primary).__name__,
                type(fallback).__name__,
                primary_error,
            )
            try:
                return await self._async_generate(fallback, prompt)
            except Exception as fallback_error:
                raise RuntimeError(
                    "Both LLM providers failed. "
                    f"Primary error: {primary_error}; "
                    f"fallback error: {fallback_error}"
                ) from fallback_error

    async def async_summarize_article(self, article: dict[str, Any]) -> str:
        """Asynchronously summarize an article, with provider fallback."""
        prompt = (
            "Summarize the following news article in 2-3 concise sentences. "
            "Preserve its key facts and do not add information.\n\n"
            f"{self._article_text(article)}"
        )
        return await self._async_generate_with_fallback(
            self.openai_provider, self.cohere_provider, prompt
        )

    async def async_analyze_sentiment(self, summary: str) -> str:
        """Asynchronously analyze a summary's sentiment, with provider fallback."""
        if not summary.strip():
            raise ValueError("summary cannot be empty")
        prompt = (
            "Analyze the sentiment of the following news summary. "
            "Label it Positive, Negative, or Neutral and briefly explain why.\n\n"
            f"{summary}"
        )
        return await self._async_generate_with_fallback(
            self.cohere_provider, self.openai_provider, prompt
        )

    async def async_process_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """Asynchronously return an article augmented with summary and sentiment."""
        summary = await self.async_summarize_article(article)
        result = dict(article)
        result["summary"] = summary
        result["sentiment"] = await self.async_analyze_sentiment(summary)
        return result

    async def async_process_articles(
        self, articles: list[dict[str, Any]], max_concurrency: int = 5
    ) -> list[dict[str, Any]]:
        """Process articles concurrently while limiting in-flight article tasks."""
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")

        semaphore = asyncio.Semaphore(max_concurrency)

        async def process(article: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self.async_process_article(article)

        return await asyncio.gather(*(process(article) for article in articles))


def main() -> int:
    """Fetch and process two technology articles, then display usage costs."""
    try:
        summarizer = NewsSummarizer()
        results = asyncio.run(
            summarizer.async_process_articles(fetch_tech_news(limit=2))
        )
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    for number, article in enumerate(results, start=1):
        source = article.get("source") or {}
        print(f"\n{number}. {article.get('title') or 'Untitled'}")
        print(f"   Source: {source.get('name') or 'Unknown'}")
        print(f"   Summary: {article['summary']}")
        print(f"   Sentiment: {article['sentiment']}")

    print("\n" + summarizer.cost_tracker.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())