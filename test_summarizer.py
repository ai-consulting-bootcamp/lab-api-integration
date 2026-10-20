
"""Unit tests for the multi-provider news summarizer."""

from unittest.mock import Mock, patch

import pytest

from llm_providers import LLMProviders
from summarizer import NewsSummarizer


# --------------------------------------------------
# Test fixtures
# --------------------------------------------------

@pytest.fixture
def sample_article():
    """Provide a sample news article."""
    return {
        "title": "Company launches new AI assistant",
        "description": "The tool automates repetitive tasks.",
        "content": "Businesses can use it to improve efficiency.",
        "source": {"name": "Tech News"},
        "url": "https://example.com/article",
    }


@pytest.fixture
def summarizer():
    """Create a summarizer without initializing real API clients."""
    with patch("summarizer.NewsAPI"), patch("summarizer.LLMProviders"):
        instance = NewsSummarizer()
        instance.providers.total_cost = 0.0
        instance.providers.config.daily_budget = 5.0
        return instance


@pytest.fixture
def providers():
    """Create provider manager without real API clients."""
    with patch("llm_providers.OpenAI"), patch("llm_providers.cohere.ClientV2"):
        instance = LLMProviders()
        instance.total_cost = 0.0
        return instance


# --------------------------------------------------
# News summarizer tests
# --------------------------------------------------

def test_process_article(summarizer, sample_article):
    """Verify article processing and output structure."""
    summarizer.providers.summarize.return_value = {
        "summary": "A company introduced an AI assistant.",
        "cost": 0.0001,
    }

    summarizer.providers.analyze_sentiment.return_value = {
        "sentiment": "Positive",
        "cost": 0.0002,
    }

    def update_cost(*args, **kwargs):
        summarizer.providers.total_cost = 0.0003
        return {
            "sentiment": "Positive",
            "cost": 0.0002,
        }

    summarizer.providers.analyze_sentiment.side_effect = update_cost

    result = summarizer.process_article(sample_article)

    assert result["title"] == sample_article["title"]
    assert result["source"] == "Tech News"
    assert result["summary"] == "A company introduced an AI assistant."
    assert result["sentiment"] == "Positive"
    assert result["cost"] == pytest.approx(0.0003)
    assert "processed_at" in result

    summarizer.providers.summarize.assert_called_once()
    summarizer.providers.analyze_sentiment.assert_called_once_with(
        result["summary"]
    )


def test_process_news(summarizer, sample_article):
    """Verify news retrieval and processing."""
    summarizer.news_api.get_top_headlines.return_value = [
        sample_article,
        sample_article,
    ]

    with patch.object(
        summarizer,
        "process_article",
        return_value={"title": "Processed"},
    ) as mock_process:
        results = summarizer.process_news(limit=2)

    assert len(results) == 2
    assert mock_process.call_count == 2

    summarizer.news_api.get_top_headlines.assert_called_once_with(
        category="technology",
        country="us",
        page_size=2,
    )


def test_no_articles(summarizer):
    """Verify handling when NewsAPI returns no articles."""
    summarizer.news_api.get_top_headlines.return_value = []

    results = summarizer.process_news()

    assert results == []


def test_invalid_article_limit(summarizer):
    """Reject an invalid article limit."""
    with pytest.raises(ValueError, match="Article limit"):
        summarizer.process_news(limit=0)


def test_article_processing_failure(summarizer, sample_article):
    """Verify failed articles do not prevent processing others."""
    summarizer.news_api.get_top_headlines.return_value = [
        sample_article,
        sample_article,
    ]

    with patch.object(
        summarizer,
        "process_article",
        side_effect=[
            ValueError("Processing failed"),
            {"title": "Successful article"},
        ],
    ):
        results = summarizer.process_news(limit=2)

    assert len(results) == 1
    assert results[0]["title"] == "Successful article"


# --------------------------------------------------
# Provider fallback tests
# --------------------------------------------------

def test_openai_to_cohere_fallback(providers):
    """Verify Cohere takes over after an OpenAI connection failure."""
    import httpx2
    from openai import APIConnectionError

    providers.summarize_with_openai = Mock(
        side_effect=APIConnectionError(
            request=httpx2.Request(
                "POST",
                "https://api.openai.com",
            )
        )
    )

    providers.summarize_with_cohere = Mock(
        return_value={
            "summary": "Fallback summary",
            "cost": 0.0005,
        }
    )

    result = providers.summarize("Sample article")

    assert result["summary"] == "Fallback summary"
    providers.summarize_with_cohere.assert_called_once()


def test_cohere_to_openai_fallback(providers):
    """Verify OpenAI takes over after a temporary Cohere failure."""
    from cohere.core.api_error import ApiError

    providers.sentiment_with_cohere = Mock(
        side_effect=ApiError(
            status_code=503,
            body="Service unavailable",
        )
    )

    providers.sentiment_with_openai = Mock(
        return_value={
            "sentiment": "Neutral",
            "cost": 0.0001,
        }
    )

    result = providers.analyze_sentiment("Sample article")

    assert result["sentiment"] == "Neutral"
    providers.sentiment_with_openai.assert_called_once()


def test_cohere_permanent_error_no_fallback(providers):
    """Verify authentication errors do not trigger fallback."""
    from cohere.core.api_error import ApiError

    providers.sentiment_with_cohere = Mock(
        side_effect=ApiError(
            status_code=401,
            body="Unauthorized",
        )
    )

    providers.sentiment_with_openai = Mock()

    with pytest.raises(ApiError):
        providers.analyze_sentiment("Sample article")

    providers.sentiment_with_openai.assert_not_called()


# --------------------------------------------------
# Reliability and cost tests
# --------------------------------------------------

def test_budget_enforcement(providers):
    """Block requests when the configured budget is reached."""
    providers.total_cost = providers.config.daily_budget

    with pytest.raises(RuntimeError, match="API budget reached"):
        providers.check_budget()


def test_budget_below_limit(providers):
    """Allow requests while spending remains below the limit."""
    providers.total_cost = 0.01
    providers.check_budget()


def test_openai_retry(providers):
    """Verify retry succeeds after temporary failures."""
    import httpx2
    from openai import APITimeoutError

    operation = Mock(
        side_effect=[
            APITimeoutError(
                request=httpx2.Request(
                    "POST",
                    "https://api.openai.com",
                )
            ),
            "Success",
        ]
    )

    with patch("time.sleep"):
        result = providers.retry_request(operation)

    assert result == "Success"
    assert operation.call_count == 2


def test_cohere_retry(providers):
    """Verify Cohere retry succeeds after a temporary failure."""
    from cohere.core.api_error import ApiError

    operation = Mock(
        side_effect=[
            ApiError(
                status_code=503,
                body="Service unavailable",
            ),
            "Success",
        ]
    )

    with patch("time.sleep"):
        result = providers.retry_cohere_request(operation)

    assert result == "Success"
    assert operation.call_count == 2


def test_rate_limiting(providers):
    """Verify the limiter waits when requests are too close."""
    providers.last_request_time = 99.5

    with (
        patch("time.monotonic", return_value=100.0),
        patch("time.sleep") as mock_sleep,
    ):
        providers.apply_rate_limit()

    mock_sleep.assert_called_once_with(0.5)
