"""Tests for provider routing, streaming controls, and workflow errors."""

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from budget import BudgetExceededError, DailyBudget
from llm_providers import LLMProviders, ProviderFailoverError
from news_api import NewsFetchError, fetch_news
from rate_limit import LocalRateLimitError, RateLimiter
from stream_control import collect_openai_stream
from summarizer import NewsSummarizer, WorkflowError


@pytest.fixture
def providers():
    """Build a provider instance without creating real API clients."""
    instance = LLMProviders.__new__(LLMProviders)
    instance.openai_client = Mock()
    instance.cohere_client = Mock()
    instance.rate_limiter = Mock()
    instance.budget = Mock()
    instance.budget.remaining_usd.return_value = Decimal("0.01")
    instance.total_cost = Decimal("0")

    # Routing tests mock these methods. Direct stream tests explicitly call
    # the original class methods instead.
    instance._stream_openai = Mock()
    instance._stream_cohere = Mock()
    return instance


def test_summarize_uses_openai_first(providers):
    providers._stream_openai.return_value = "A short summary."

    assert providers.summarize("News input") == "A short summary."
    providers._stream_openai.assert_called_once()
    providers._stream_cohere.assert_not_called()


def test_summarize_falls_back_to_cohere(providers):
    providers._stream_openai.side_effect = RuntimeError(
        "OpenAI unavailable"
    )
    providers._stream_cohere.return_value = "Fallback summary."

    assert providers.summarize("News input") == "Fallback summary."
    providers._stream_cohere.assert_called_once()


def test_sentiment_uses_cohere_first(providers):
    providers._stream_cohere.return_value = "positive"

    assert providers.analyze_sentiment("A good summary") == "positive"
    providers._stream_cohere.assert_called_once()
    providers._stream_openai.assert_not_called()


def test_sentiment_falls_back_to_openai(providers):
    providers._stream_cohere.side_effect = RuntimeError(
        "Cohere unavailable"
    )
    providers._stream_openai.return_value = "negative"

    assert providers.analyze_sentiment("A troubling summary") == "negative"
    providers._stream_openai.assert_called_once()


def test_cost_summary_starts_at_zero(providers):
    assert providers.get_cost_summary() == {
        "estimated_total_usd": 0.0,
        "remaining_daily_usd": 0.01,
    }


def test_summarize_reports_failure_of_both_providers(providers):
    providers._stream_openai.side_effect = RuntimeError(
        "OpenAI unavailable"
    )
    providers._stream_cohere.side_effect = RuntimeError(
        "Cohere unavailable"
    )

    with pytest.raises(ProviderFailoverError) as error:
        providers.summarize("News input")

    assert error.value.task == "Summarization"
    assert isinstance(error.value.primary_error, RuntimeError)
    assert isinstance(error.value.fallback_error, RuntimeError)


def test_sentiment_reports_failure_of_both_providers(providers):
    providers._stream_cohere.side_effect = RuntimeError(
        "Cohere unavailable"
    )
    providers._stream_openai.side_effect = RuntimeError(
        "OpenAI unavailable"
    )

    with pytest.raises(ProviderFailoverError) as error:
        providers.analyze_sentiment("News summary")

    assert error.value.task == "Sentiment analysis"
    assert isinstance(error.value.primary_error, RuntimeError)
    assert isinstance(error.value.fallback_error, RuntimeError)


def test_fetch_news_rejects_empty_query():
    with pytest.raises(ValueError, match="query cannot be empty"):
        fetch_news("   ")


def test_fetch_news_rejects_article_count_out_of_range():
    with pytest.raises(ValueError, match="between 1 and 5"):
        fetch_news("technology", articles=0)


def test_summarizer_converts_news_error_to_workflow_error(monkeypatch):
    def fail_fetch_news(query, articles=3):
        raise NewsFetchError("AskNews unavailable")

    monkeypatch.setattr("summarizer.fetch_news", fail_fetch_news)

    instance = NewsSummarizer.__new__(NewsSummarizer)
    instance.providers = Mock()

    with pytest.raises(WorkflowError, match="AskNews unavailable"):
        instance.process_news("technology", articles=2)

    instance.providers.summarize.assert_not_called()


def test_rate_limit_blocks_api_without_fallback(providers):
    providers._stream_openai.side_effect = LocalRateLimitError(
        "Limit reached"
    )

    with pytest.raises(LocalRateLimitError, match="Limit reached"):
        providers.summarize("News input")

    providers._stream_cohere.assert_not_called()


def test_rate_limiter_persists_across_instances(tmp_path):
    database = tmp_path / "rate-limit.sqlite3"

    RateLimiter(limit=2, database=database).acquire()
    RateLimiter(limit=2, database=database).acquire()

    with pytest.raises(LocalRateLimitError):
        RateLimiter(limit=2, database=database).acquire()


def test_stream_stops_and_closes_on_budget_error():
    budget = Mock()
    budget.check_stream_cost.side_effect = BudgetExceededError(
        "Limit reached"
    )
    chunk = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(delta=SimpleNamespace(content="partial"))
        ],
    )
    stream = Mock()
    stream.__iter__ = Mock(return_value=iter([chunk]))

    with pytest.raises(BudgetExceededError, match="Limit reached"):
        collect_openai_stream(
            stream,
            budget,
            "test-reservation",
            10,
            Decimal("0.15"),
            Decimal("0.60"),
        )

    stream.close.assert_called_once()


def test_daily_budget_persists_and_releases_unused_reservation(tmp_path):
    database = tmp_path / "budget.sqlite3"
    first = DailyBudget("0.01", database)
    reservation = first.reserve("0.008")

    second = DailyBudget("0.01", database)
    assert second.remaining_usd() == Decimal("0.002")

    second.settle(reservation, "0.001")
    assert first.remaining_usd() == Decimal("0.009")


def test_budget_blocks_request_before_openai_api_call(providers, tmp_path):
    providers.budget = DailyBudget(
        "0.000001", tmp_path / "budget.sqlite3"
    )

    with pytest.raises(BudgetExceededError):
        LLMProviders._stream_openai(
            providers,
            "News input",
            providers.SUMMARY_PROMPT,
            providers.SUMMARY_TOKENS,
        )

    providers.openai_client.chat.completions.create.assert_not_called()


def test_openai_stream_settles_reported_usage(providers):
    providers.budget.reserve.return_value = "reservation-1"
    text_chunk = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content="A short summary.")
            )
        ],
    )
    usage_chunk = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=5,
        ),
        choices=[],
    )
    stream = Mock()
    stream.__iter__ = Mock(
        return_value=iter([text_chunk, usage_chunk])
    )
    providers.openai_client.chat.completions.create.return_value = stream

    result = LLMProviders._stream_openai(
        providers,
        "News input",
        providers.SUMMARY_PROMPT,
        providers.SUMMARY_TOKENS,
    )

    assert result == "A short summary."
    providers.budget.settle.assert_called_once()
    assert providers.total_cost > 0
    stream.close.assert_called_once()

def test_sentiment_accepts_one_label_inside_a_sentence(providers):
    providers._stream_cohere.return_value = (
        "The sentiment of the text is **positive**."
    )

    assert providers.analyze_sentiment("News summary") == "positive"
    providers._stream_openai.assert_not_called()


def test_ambiguous_sentiment_uses_fallback(providers):
    providers._stream_cohere.return_value = (
        "It could be positive or negative."
    )
    providers._stream_openai.return_value = "neutral"

    assert providers.analyze_sentiment("News summary") == "neutral"
    providers._stream_openai.assert_called_once()
