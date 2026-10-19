"""Streaming OpenAI/Cohere calls with fallback, rate and budget controls."""

import re
import logging
import os
from decimal import Decimal
from pathlib import Path

import cohere
from openai import OpenAI

from budget import BudgetExceededError, DailyBudget
from config import settings
from rate_limit import LocalRateLimitError, RateLimiter
from stream_control import collect_cohere_stream, collect_openai_stream

logger = logging.getLogger(__name__)


class ProviderFailoverError(RuntimeError):
    """Raised when both providers fail at the same task."""

    def __init__(
        self,
        task: str,
        primary_error: Exception,
        fallback_error: Exception,
    ) -> None:
        self.task = task
        self.primary_error = primary_error
        self.fallback_error = fallback_error
        super().__init__(
            f"{task} failed on the primary and fallback providers "
            f"({type(primary_error).__name__}, "
            f"{type(fallback_error).__name__})."
        )


class LLMProviders:
    """Stream AI tasks, enforce local controls, and estimate costs."""

    OPENAI_MODEL = "gpt-4o-mini"
    OPENAI_INPUT_PER_1M = Decimal("0.15")
    OPENAI_OUTPUT_PER_1M = Decimal("0.60")

    COHERE_MODEL = "command-r7b-12-2024"
    COHERE_INPUT_PER_1M = Decimal("0.15")
    COHERE_OUTPUT_PER_1M = Decimal("0.15")

    SUMMARY_TOKENS = 180
    SENTIMENT_TOKENS = 10

    SUMMARY_PROMPT = "Summarize the news clearly in 2-3 sentences."
    SENTIMENT_PROMPT = (
        "Classify the sentiment as positive, negative, or neutral. "
        "Return only one of those labels."
    )

    def __init__(self) -> None:
        """Create clients and persistent local controls."""
        if not settings.openai_api_key or not settings.cohere_api_key:
            raise ValueError("OPENAI_API_KEY and COHERE_API_KEY are required.")

        # SDK retries are disabled here: every app-level request should pass
        # through our rate and budget checks first.
        self.openai_client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.request_timeout,
            max_retries=0,
        )
        self.cohere_client = cohere.ClientV2(api_key=settings.cohere_api_key)
        self.rate_limiter = RateLimiter(
            limit=int(os.getenv("MAX_LLM_REQUESTS_PER_MINUTE", "10")),
            database=Path(__file__).with_name(".llm-rate-limit.sqlite3"),
        )
        self.budget = DailyBudget(
            limit_usd=str(settings.daily_budget),
            database=Path(__file__).with_name(".llm-budget.sqlite3"),
        )
        self.total_cost = Decimal("0")

    @staticmethod
    def _estimate_input_tokens(system: str, text: str) -> int:
        """Use UTF-8 bytes plus overhead as a cautious input estimate."""
        return len((system + text).encode("utf-8")) + 128

    @staticmethod
    def _estimated_cost(
        input_tokens: int,
        output_tokens: int,
        input_price: Decimal,
        output_price: Decimal,
    ) -> Decimal:
        return (
            Decimal(str(input_tokens)) * input_price
            + Decimal(str(output_tokens)) * output_price
        ) / Decimal(1_000_000)

    def _stream_openai(
        self, text: str, system: str, max_tokens: int
    ) -> str:
        """Make one budgeted streaming OpenAI request."""
        input_estimate = self._estimate_input_tokens(system, text)
        reserved = self._estimated_cost(
            input_estimate,
            max_tokens + 8,
            self.OPENAI_INPUT_PER_1M,
            self.OPENAI_OUTPUT_PER_1M,
        )

        self.rate_limiter.acquire()
        reservation_id = self.budget.reserve(reserved)

        stream = self.openai_client.chat.completions.create(
            model=self.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        result = collect_openai_stream(
            stream,
            self.budget,
            reservation_id,
            input_estimate,
            self.OPENAI_INPUT_PER_1M,
            self.OPENAI_OUTPUT_PER_1M,
        )

        # Usage is usually sent in the final chunk. If absent, keep the
        # reservation instead of reporting an unjustified zero cost.
        if result.usage is not None:
            actual = self._estimated_cost(
                result.usage.prompt_tokens,
                result.usage.completion_tokens,
                self.OPENAI_INPUT_PER_1M,
                self.OPENAI_OUTPUT_PER_1M,
            )
            self.budget.settle(reservation_id, actual)
            self.total_cost += actual
        else:
            self.total_cost += reserved
            logger.warning("OpenAI stream ended without usage metadata")

        if not result.text:
            raise ValueError("OpenAI returned an empty response.")
        return result.text

    def _stream_cohere(
        self, text: str, system: str, max_tokens: int
    ) -> str:
        """Make one budgeted streaming Cohere request."""
        input_estimate = self._estimate_input_tokens(system, text)
        reserved = self._estimated_cost(
            input_estimate,
            max_tokens + 8,
            self.COHERE_INPUT_PER_1M,
            self.COHERE_OUTPUT_PER_1M,
        )

        self.rate_limiter.acquire()
        reservation_id = self.budget.reserve(reserved)

        stream = self.cohere_client.chat_stream(
            model=self.COHERE_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            max_tokens=max_tokens,
        )
        result = collect_cohere_stream(
            stream,
            self.budget,
            reservation_id,
            input_estimate,
            self.COHERE_INPUT_PER_1M,
            self.COHERE_OUTPUT_PER_1M,
        )

        billed = getattr(result.usage, "billed_units", None)
        if billed is not None:
            actual = self._estimated_cost(
                billed.input_tokens,
                billed.output_tokens,
                self.COHERE_INPUT_PER_1M,
                self.COHERE_OUTPUT_PER_1M,
            )
            self.budget.settle(reservation_id, actual)
            self.total_cost += actual
        else:
            self.total_cost += reserved
            logger.warning("Cohere stream ended without billed usage")

        if not result.text:
            raise ValueError("Cohere returned an empty response.")
        return result.text

    def summarize(self, text: str) -> str:
        """Summarize with OpenAI; use Cohere if OpenAI fails."""
        try:
            return self._stream_openai(
                text, self.SUMMARY_PROMPT, self.SUMMARY_TOKENS
            )
        except (BudgetExceededError, LocalRateLimitError):
            raise
        except Exception as primary_error:
            logger.warning(
                "OpenAI summarization failed; trying Cohere (%s)",
                type(primary_error).__name__,
            )
            try:
                return self._stream_cohere(
                    text, self.SUMMARY_PROMPT, self.SUMMARY_TOKENS
                )
            except (BudgetExceededError, LocalRateLimitError):
                raise
            except Exception as fallback_error:
                raise ProviderFailoverError(
                    "Summarization", primary_error, fallback_error
                ) from fallback_error

    @staticmethod
    def _normalize_sentiment(text: str) -> str:
        """Accept an unambiguous label even inside a short explanation."""
        labels = set(
            re.findall(r"\b(?:positive|negative|neutral)\b", text.lower())
        )
        if len(labels) != 1:
            raise ValueError("Sentiment response has no unique label.")
        return labels.pop()

    def analyze_sentiment(self, text: str) -> str:
        """Classify with Cohere; use OpenAI for errors or ambiguous output."""
        try:
            response = self._stream_cohere(
                text, self.SENTIMENT_PROMPT, self.SENTIMENT_TOKENS
            )
            return self._normalize_sentiment(response)
        except (BudgetExceededError, LocalRateLimitError):
            raise
        except Exception as primary_error:
            logger.warning(
                "Cohere sentiment failed or was ambiguous; "
                "trying OpenAI (%s)",
                type(primary_error).__name__,
            )
            try:
                response = self._stream_openai(
                    text, self.SENTIMENT_PROMPT, self.SENTIMENT_TOKENS
                )
                return self._normalize_sentiment(response)
            except (BudgetExceededError, LocalRateLimitError):
                raise
            except Exception as fallback_error:
                raise ProviderFailoverError(
                    "Sentiment analysis", primary_error, fallback_error
                ) from fallback_error

    def get_cost_summary(self) -> dict[str, float]:
        """Return this run's estimated AI cost and today's remaining budget."""
        return {
            "estimated_total_usd": round(float(self.total_cost), 6),
            "remaining_daily_usd": round(
                float(self.budget.remaining_usd()), 6
            ),
        }


if __name__ == "__main__":
    providers = LLMProviders()
    sample = (
        "A technology company reported growth, while analysts warned "
        "that rising costs could reduce future profits."
    )
    summary = providers.summarize(sample)
    sentiment = providers.analyze_sentiment(summary)
    print("Summary:", summary)
    print("Sentiment:", sentiment)
    print("Cost:", providers.get_cost_summary())