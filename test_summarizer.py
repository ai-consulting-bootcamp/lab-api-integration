"""Unit tests for the news summarizer. No real API calls are made."""
from unittest.mock import Mock

import pytest

from config import Config
from llm_providers import (
    BudgetExceededError,
    CostTracker,
    LLMProvider,
    ProviderWithFallback,
    RateLimiter,
)
from news_api import NewsAPI
from summarizer import NewsSummarizer


# ---------- Helpers ----------

@pytest.fixture(autouse=True)
def fast_and_predictable(monkeypatch):
    """Skip real waiting and fix the retry count for every test."""
    monkeypatch.setattr("llm_providers.time.sleep", lambda seconds: None)
    monkeypatch.setattr(Config, "MAX_RETRIES", 3)


class FakeProvider(LLMProvider):
    """Provider that returns scripted responses instead of calling an API.

    Each response is either (text, input_tokens, output_tokens)
    or an Exception to raise.
    """

    name = "fake"

    def __init__(self, responses, tracker=None):
        super().__init__(
            "gpt-4o-mini",
            tracker or CostTracker(daily_budget=1.0),
            RateLimiter(max_calls=100),
        )
        self.responses = list(responses)

    def _call(self, prompt, max_tokens):
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_article(title="Test title", description="Test description"):
    """Build a cleaned article dict like NewsAPI returns."""
    return {
        "title": title,
        "description": description,
        "content": "",
        "url": "https://example.com",
        "source": "Example",
        "published_at": "2026-10-19T12:00:00Z",
    }


# ---------- Cost tracking ----------

def test_calculate_cost_known_model():
    """1,000 input + 1,000 output tokens on gpt-4o-mini."""
    cost = CostTracker.calculate_cost("gpt-4o-mini", 1000, 1000)
    assert cost == pytest.approx((1000 * 0.15 + 1000 * 0.60) / 1_000_000)


def test_calculate_cost_unknown_model_uses_default_price():
    """Unknown models use the high default price, never zero."""
    cost = CostTracker.calculate_cost("mystery-model", 1_000_000, 0)
    assert cost == pytest.approx(5.00)


def test_record_adds_up_costs():
    tracker = CostTracker(daily_budget=1.0)
    tracker.record("openai", "gpt-4o-mini", 1000, 1000)
    tracker.record("openai", "gpt-4o-mini", 1000, 1000)
    stats = tracker.summary()
    assert stats["total_requests"] == 2
    assert stats["total_cost"] == pytest.approx(2 * 0.00075)


def test_budget_exceeded_raises():
    tracker = CostTracker(daily_budget=0.001)
    tracker.total_cost = 0.001
    with pytest.raises(BudgetExceededError):
        tracker.check_budget()


# ---------- Rate limiting ----------

def test_rate_limiter_waits_when_limit_reached(monkeypatch):
    fake_sleep = Mock()
    monkeypatch.setattr("llm_providers.time.sleep", fake_sleep)
    limiter = RateLimiter(max_calls=2, period=60)

    limiter.wait_if_needed()
    limiter.wait_if_needed()
    fake_sleep.assert_not_called()

    limiter.wait_if_needed()  # third call within 60s must wait
    fake_sleep.assert_called_once()
    assert fake_sleep.call_args[0][0] > 0


# ---------- Retries and fallback ----------

def test_provider_retries_then_succeeds():
    provider = FakeProvider([TimeoutError("blip"), ("hello", 10, 5)])
    assert provider.complete("hi") == "hello"
    assert provider.cost_tracker.summary()["total_requests"] == 1


def test_provider_gives_up_after_max_retries():
    provider = FakeProvider([TimeoutError("down")] * 3)
    with pytest.raises(RuntimeError):
        provider.complete("hi")


def test_fallback_uses_backup_when_primary_fails():
    primary = FakeProvider([TimeoutError("down")] * 3)
    backup = FakeProvider([("backup answer", 10, 5)])
    backup.name = "backup"
    text, used = ProviderWithFallback(primary, backup).complete("hi")
    assert text == "backup answer"
    assert used == "backup"


def test_fallback_not_used_when_budget_exceeded():
    """Running out of budget must stop, not switch providers."""
    tracker = CostTracker(daily_budget=0.0)
    primary = FakeProvider([("never used", 1, 1)], tracker)
    backup = Mock()
    with pytest.raises(BudgetExceededError):
        ProviderWithFallback(primary, backup).complete("hi")
    backup.complete.assert_not_called()


# ---------- News API ----------

def test_news_api_cleans_and_filters_articles(monkeypatch):
    fake_response = Mock()
    fake_response.json.return_value = {
        "status": "ok",
        "articles": [
            {"title": "Real story", "description": None,
             "url": "https://a.com", "source": {"name": "A"},
             "publishedAt": "2026-10-19"},
            {"title": "[Removed]", "description": "gone"},
        ],
    }
    monkeypatch.setattr("news_api.requests.get", Mock(return_value=fake_response))

    articles = NewsAPI(api_key="test").fetch_top_headlines()

    assert len(articles) == 1  # [Removed] filtered out
    assert articles[0]["title"] == "Real story"
    assert articles[0]["description"] == ""  # None became ""
    assert articles[0]["source"] == "A"


def test_news_api_returns_empty_list_on_error(monkeypatch):
    fake_response = Mock()
    fake_response.json.return_value = {"status": "error", "message": "bad key"}
    monkeypatch.setattr("news_api.requests.get", Mock(return_value=fake_response))
    assert NewsAPI(api_key="test").fetch_top_headlines() == []


# ---------- Summarizer ----------

@pytest.mark.parametrize("raw, expected_label", [
    ("positive - good news for users", "positive"),
    ("Negative - layoffs announced", "negative"),
    ("**neutral** - just a product update", "neutral"),
    ("I think this is fine", "unknown"),
])
def test_parse_sentiment(raw, expected_label):
    label, _ = NewsSummarizer.parse_sentiment(raw)
    assert label == expected_label


def test_build_article_text_handles_empty_description():
    article = make_article(description="")
    assert NewsSummarizer.build_article_text(article) == "Test title"


def make_summarizer(articles):
    """NewsSummarizer wired to fakes only."""
    news_api = Mock()
    news_api.fetch_top_headlines.return_value = articles
    summary_provider = Mock()
    summary_provider.complete.return_value = ("A short summary.", "openai")
    sentiment_provider = Mock()
    sentiment_provider.complete.return_value = ("positive - good news", "cohere")
    return NewsSummarizer(
        news_api=news_api,
        cost_tracker=CostTracker(daily_budget=1.0),
        summary_provider=summary_provider,
        sentiment_provider=sentiment_provider,
    )


def test_process_article_builds_full_record():
    record = make_summarizer([]).process_article(make_article())
    assert record["summary"] == "A short summary."
    assert record["sentiment"] == "positive"
    assert record["summary_provider"] == "openai"
    assert record["sentiment_provider"] == "cohere"
    assert record["processed_at"]


def test_process_articles_skips_failed_article():
    summarizer = make_summarizer([make_article("One"), make_article("Two")])
    summarizer.summary_provider.complete.side_effect = [
        RuntimeError("both providers down"),
        ("Summary two.", "openai"),
    ]
    results = summarizer.process_articles(max_articles=2)
    assert len(results) == 1
    assert results[0]["title"] == "Two"


def test_process_articles_stops_on_budget():
    summarizer = make_summarizer([make_article("One"), make_article("Two")])
    summarizer.summary_provider.complete.side_effect = BudgetExceededError("spent")
    assert summarizer.process_articles(max_articles=2) == []