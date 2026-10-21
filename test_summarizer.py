"""
test_summarizer.py - Unit tests for the News Summarizer.
"""

from unittest.mock import MagicMock, patch

import pytest

from config import Config
from llm_providers import (CircuitBreaker, LLMProviders, ProductionAPIClient, RateLimiter,
                           TokenBudgetManager, exponential_backoff_with_jitter)
from news_api import fetch_news
from summarizer import NewsSummarizer

ARTICLE = {"title": "Chip maker raises outlook", "source": "Test News",
           "description": "Strong AI demand lifts forecast.", "content": "",
           "url": "https://example.com", "published_at": "2026-10-21T08:00:00Z"}



class SimulatedAPIFailure:
    """Simulate API failures for testing retry logic."""

    def __init__(self, fail_count=2):
        self.fail_count = fail_count
        self.call_count = 0

    def call(self, prompt=None):
        """Fail fail_count times, then succeed."""
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise Exception(f"Simulated API failure (attempt {self.call_count})")
        return {"response": "Success! API call worked.", "usage": {}, "model": "test"}


class FailingService:
    """A service that fails multiple times then recovers."""

    def __init__(self, fail_until=5):
        self.call_count = 0
        self.fail_until = fail_until

    def call(self):
        """Simulate a service call."""
        self.call_count += 1
        if self.call_count <= self.fail_until:
            raise Exception(f"Service failure (call {self.call_count})")
        return f"Success! (call {self.call_count})"


def fake_result(provider, text="ok"):
    """A provider result shaped like ask_*_with_budget returns."""
    return {"response": text, "usage": {"input_tokens": 10, "output_tokens": 5},
            "provider": provider, "model": "test-model"}


# ---------- Config ----------

def test_config_validate_passes_with_keys(monkeypatch):
    for key in ["OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY"]:
        monkeypatch.setenv(key, "test-key")
    assert Config().validate() is True


def test_config_validate_reports_missing_keys(monkeypatch):
    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NEWS_API_KEY"):
        Config().validate()


def test_config_environment_settings(monkeypatch):
    monkeypatch.delenv("MAX_RETRIES", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)
    assert Config("production").openai_model == "gpt-4o"
    assert Config("development").max_retries == 2


# ---------- Exponential backoff with jitter ----------

def test_backoff_with_jitter_stays_within_bounds():
    for attempt in range(6):
        delay = exponential_backoff_with_jitter(attempt, base_delay=1, max_delay=10)
        assert 0 <= delay <= min(2 ** attempt, 10)


def test_jittered_retry_recovers_from_transient_failures():
    simulator = SimulatedAPIFailure(fail_count=2)
    client = ProductionAPIClient(simulator.call, failure_threshold=5, max_retries=3)
    with patch("llm_providers.time.sleep"):
        result = client.call("hi")
    assert result["response"] == "Success! API call worked."
    assert simulator.call_count == 3


def test_budget_error_is_not_retried():
    func = MagicMock(side_effect=Exception("Token budget exceeded! ..."))
    client = ProductionAPIClient(func, max_retries=3)
    with pytest.raises(Exception, match="Token budget exceeded"):
        client.call("hi")
    assert func.call_count == 1


# ---------- Circuit breaker ----------

def test_circuit_breaker_opens_and_fails_fast():
    breaker = CircuitBreaker(failure_threshold=3, timeout=10)
    service = FailingService(fail_until=5)
    for _ in range(3):
        with pytest.raises(Exception):
            breaker.call(service.call)
    assert breaker.get_status()["state"] == "open"

    # Open circuit: fails fast without calling the service
    with pytest.raises(Exception, match="OPEN"):
        breaker.call(service.call)
    assert service.call_count == 3


def test_circuit_breaker_half_open_recovers():
    breaker = CircuitBreaker(failure_threshold=1, timeout=0)
    service = FailingService(fail_until=1)
    with pytest.raises(Exception):
        breaker.call(service.call)
    assert breaker.call(service.call) == "Success! (call 2)"
    assert breaker.get_status()["state"] == "closed"


# ---------- Token budget manager ----------

def test_calculate_cost_uses_exact_tokens():
    manager = TokenBudgetManager(daily_budget=10.0)
    cost = manager.calculate_cost("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.75)


def test_track_request_updates_usage():
    manager = TokenBudgetManager(daily_budget=10.0)
    manager.track_request("cohere", "command-r-08-2024", 1000, 500)
    summary = manager.get_summary()
    assert summary["provider_usage"]["cohere"]["input_tokens"] == 1000
    assert summary["used_budget"] == pytest.approx(0.00045)


def test_budget_exceeded_raises():
    manager = TokenBudgetManager(daily_budget=0.001)
    with pytest.raises(Exception, match="Token budget exceeded"):
        manager.track_request("openai", "gpt-4o", 1000, 1000)


# ---------- Fallback ----------

def make_providers():
    """LLMProviders with both clients mocked."""
    providers = LLMProviders(budget_manager=TokenBudgetManager(10.0))
    providers.clients = {"openai": MagicMock(), "cohere": MagicMock()}
    return providers


def test_fallback_used_when_primary_fails():
    providers = make_providers()
    providers.clients["openai"].call.side_effect = Exception("OpenAI down")
    providers.clients["cohere"].call.return_value = fake_result("cohere")
    result = providers.ask_with_fallback("hi", primary="openai", secondary="cohere")
    assert result["provider"] == "cohere"
    assert result["fallback_used"] is True


def test_no_fallback_when_primary_works():
    providers = make_providers()
    providers.clients["openai"].call.return_value = fake_result("openai")
    result = providers.ask_with_fallback("hi")
    assert result["fallback_used"] is False
    providers.clients["cohere"].call.assert_not_called()


def test_all_providers_failed():
    providers = make_providers()
    providers.clients["openai"].call.side_effect = Exception("down")
    providers.clients["cohere"].call.side_effect = Exception("down")
    with pytest.raises(Exception, match="All providers failed"):
        providers.ask_with_fallback("hi")


# ---------- Summarizer ----------

def make_summarizer():
    """NewsSummarizer with mocked providers: OpenAI summarizes, Cohere rates sentiment."""
    providers = MagicMock()
    providers.ask_with_fallback.side_effect = lambda prompt, primary, secondary: {
        **fake_result(primary, "AI demand lifts chip outlook." if primary == "openai"
                      else "1. Sentiment: positive\n2. Growth news"),
        "fallback_used": False
    }
    return NewsSummarizer(budget_manager=TokenBudgetManager(10.0), providers=providers)


def test_openai_summary_is_passed_to_cohere():
    summarizer = make_summarizer()
    result = summarizer.process_article(ARTICLE)
    assert result["providers"] == {"summary": "openai", "sentiment": "cohere"}
    sentiment_prompt = summarizer.providers.ask_with_fallback.call_args_list[1].args[0]
    assert "AI demand lifts chip outlook." in sentiment_prompt


def test_failed_article_does_not_stop_batch():
    summarizer = make_summarizer()
    summarizer.process_article = MagicMock(side_effect=[Exception("boom"), {"ok": True}])
    assert summarizer.process_articles([ARTICLE, ARTICLE]) == [{"ok": True}]


def test_batch_stops_when_budget_used_up():
    summarizer = make_summarizer()
    summarizer.budget_manager.used_budget = 10.0
    summarizer.process_article = MagicMock()
    assert summarizer.process_articles([ARTICLE]) == []
    summarizer.process_article.assert_not_called()


# ---------- News API and rate limiting ----------

def test_fetch_news_maps_asknews_articles():
    item = MagicMock(eng_title="Real story", title="Real story", domain_url="example.com",
                     summary="Short summary", key_points=["Point one", "Point two"],
                     article_url="https://example.com/a", pub_date=None)
    empty = MagicMock(title="")
    sdk = MagicMock()
    sdk.return_value.news.search_news.return_value = MagicMock(as_dicts=[item, empty])
    with patch("news_api.AskNewsSDK", sdk), patch("news_api.news_rate_limiter"):
        articles = fetch_news(category="technology", page_size=2, api_key="test")
    assert [a["title"] for a in articles] == ["Real story"]
    assert articles[0]["content"] == "Point one Point two"
    assert sdk.return_value.news.search_news.call_args.kwargs["categories"] == ["Technology"]


def test_fetch_news_returns_empty_list_on_error():
    sdk = MagicMock(side_effect=Exception("network down"))
    with patch("news_api.AskNewsSDK", sdk), patch("news_api.news_rate_limiter"):
        assert fetch_news(api_key="test") == []


def test_rate_limiter_waits_between_requests():
    limiter = RateLimiter(requests_per_minute=60)
    with patch("llm_providers.time.sleep") as mock_sleep:
        limiter.wait()
        limiter.wait()
    assert mock_sleep.called
