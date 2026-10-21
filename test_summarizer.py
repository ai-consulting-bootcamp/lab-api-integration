from types import SimpleNamespace

import pytest

from config import Config
from llm_providers import CostTracker, ProviderError, ProviderResponse, ask_with_fallback
from summarizer import NewsSummarizer


class FakeProvider:
    def __init__(self, name, answer="neutral", failures=0):
        self.name = name
        self.answer = answer
        self.failures = failures

    def complete(self, prompt):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary failure")
        return ProviderResponse(self.answer, self.name, 0.01)


def test_fallback_uses_second_provider_after_primary_failure():
    result = ask_with_fallback("test", FakeProvider("primary", failures=1), FakeProvider("fallback"), retries=1, sleep=lambda _: None)
    assert result.provider == "fallback"


def test_budget_is_enforced():
    tracker = CostTracker(0.01)
    tracker.add(0.01)
    with pytest.raises(ProviderError):
        tracker.add(0.01)


def test_workflow_passes_summary_to_sentiment_provider():
    summary = FakeProvider("summary", "A short summary")
    sentiment = FakeProvider("sentiment", "positive")
    workflow = NewsSummarizer(
        Config(max_retries=1, daily_budget=1),
        news_client=SimpleNamespace(top_headlines=lambda **_: [{"title": "News", "content": "Article text"}]),
        summary_provider=summary,
        sentiment_provider=sentiment,
    )
    result = workflow.run(limit=1)
    assert result[0]["summary"] == "A short summary"
    assert result[0]["sentiment"] == "positive"

