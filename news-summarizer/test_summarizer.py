"""Unit tests for synchronous and asynchronous article summarization."""

import asyncio
import threading
import time
from typing import Any, Callable

import pytest

import main as main_module
import summarizer as summarizer_module
from llm_providers import CostTracker
from summarizer import NewsSummarizer


class StubProvider:
    """Provider test double that records prompts and can simulate failures."""

    def __init__(
        self,
        responses: list[str] | None = None,
        error: Exception | None = None,
        delay: float = 0,
        response_for: Callable[[str], str] | None = None,
    ) -> None:
        self.responses = responses or []
        self.error = error
        self.delay = delay
        self.response_for = response_for
        self.prompts: list[str] = []
        self.active_calls = 0
        self.max_active_calls = 0
        self._lock = threading.Lock()

    def generate(self, prompt: str) -> str:
        with self._lock:
            self.prompts.append(prompt)
            self.active_calls += 1
            self.max_active_calls = max(self.max_active_calls, self.active_calls)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.error is not None:
                raise self.error
            if self.response_for is not None:
                return self.response_for(prompt)
            if not self.responses:
                raise AssertionError("No stub response configured.")
            return self.responses.pop(0)
        finally:
            with self._lock:
                self.active_calls -= 1


def make_summarizer(
    openai: StubProvider | None = None,
    cohere: StubProvider | None = None,
    cost_tracker: CostTracker | None = None,
) -> NewsSummarizer:
    """Build a summarizer with fake providers and no pacing delay."""
    return NewsSummarizer(
        openai_provider=openai or StubProvider(["summary"]),
        cohere_provider=cohere or StubProvider(["neutral"]),
        cost_tracker=cost_tracker,
        request_interval=0,
    )


def test_summarize_article_uses_article_fields_and_openai() -> None:
    openai = StubProvider(["Concise summary."])
    summarizer = make_summarizer(openai=openai)

    result = summarizer.summarize_article(
        {"title": "  Headline  ", "description": "Details", "content": None}
    )

    assert result == "Concise summary."
    assert "Headline\nDetails" in openai.prompts[0]
    assert "2-3 concise sentences" in openai.prompts[0]


def test_summarize_article_rejects_missing_text() -> None:
    summarizer = make_summarizer()

    with pytest.raises(ValueError, match="Article must include"):
        summarizer.summarize_article({"title": "  ", "description": None})


def test_analyze_sentiment_rejects_empty_summary() -> None:
    summarizer = make_summarizer()

    with pytest.raises(ValueError, match="summary cannot be empty"):
        summarizer.analyze_sentiment(" \n ")


def test_process_article_returns_copy_with_summary_and_sentiment() -> None:
    original: dict[str, Any] = {"title": "Headline", "source": {"name": "Example"}}
    summarizer = make_summarizer(
        openai=StubProvider(["Article summary."]),
        cohere=StubProvider(["Neutral: factual reporting."]),
    )

    result = summarizer.process_article(original)

    assert result == {
        "title": "Headline",
        "source": {"name": "Example"},
        "summary": "Article summary.",
        "sentiment": "Neutral: factual reporting.",
    }
    assert "summary" not in original
    assert "sentiment" not in original


def test_primary_provider_failure_uses_fallback(caplog: pytest.LogCaptureFixture) -> None:
    openai = StubProvider(error=RuntimeError("OpenAI unavailable"))
    cohere = StubProvider(["Fallback summary."])
    summarizer = make_summarizer(openai=openai, cohere=cohere)

    assert summarizer.summarize_article({"title": "Headline"}) == "Fallback summary."
    assert len(openai.prompts) == 1
    assert len(cohere.prompts) == 1
    assert "retrying with" in caplog.text


def test_both_providers_failing_raises_runtime_error() -> None:
    summarizer = make_summarizer(
        openai=StubProvider(error=RuntimeError("OpenAI unavailable")),
        cohere=StubProvider(error=RuntimeError("Cohere unavailable")),
    )

    with pytest.raises(RuntimeError, match="Both LLM providers failed") as error:
        summarizer.summarize_article({"title": "Headline"})

    assert "OpenAI unavailable" in str(error.value)
    assert "Cohere unavailable" in str(error.value)


def test_generation_stops_when_daily_budget_is_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(summarizer_module, "DAILY_BUDGET", 0.0)
    openai = StubProvider(["Summary"])
    summarizer = make_summarizer(openai=openai)

    with pytest.raises(RuntimeError, match="Daily budget"):
        summarizer._generate(openai, "prompt")

    assert openai.prompts == []


def test_async_process_articles_preserves_order_and_processes_concurrently() -> None:
    openai = StubProvider(["First summary", "Second summary"], delay=0.05)
    cohere = StubProvider(
        delay=0.05,
        response_for=lambda prompt: (
            "First sentiment" if "First summary" in prompt else "Second sentiment"
        ),
    )
    summarizer = make_summarizer(openai=openai, cohere=cohere)

    results = asyncio.run(
        summarizer.async_process_articles(
            [{"title": "First"}, {"title": "Second"}], max_concurrency=2
        )
    )

    assert [article["title"] for article in results] == ["First", "Second"]
    assert [article["summary"] for article in results] == [
        "First summary",
        "Second summary",
    ]
    assert [article["sentiment"] for article in results] == [
        "First sentiment",
        "Second sentiment",
    ]
    assert openai.max_active_calls == 2


def test_async_process_articles_rejects_invalid_concurrency() -> None:
    summarizer = make_summarizer()

    with pytest.raises(ValueError, match="max_concurrency must be at least 1"):
        asyncio.run(summarizer.async_process_articles([], max_concurrency=0))


def test_async_summarization_uses_fallback() -> None:
    summarizer = make_summarizer(
        openai=StubProvider(error=RuntimeError("OpenAI unavailable")),
        cohere=StubProvider(["Fallback summary."]),
    )

    result = asyncio.run(summarizer.async_summarize_article({"title": "Headline"}))

    assert result == "Fallback summary."


def test_prompt_article_limit_retries_invalid_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter(["not a number", "9", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert main_module.prompt_article_limit() == 2
    output = capsys.readouterr().out
    assert "Enter a whole number" in output
    assert "Choose a number" in output


def test_main_fetches_processes_and_displays_articles(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeTracker:
        def summary(self) -> str:
            return "Usage summary"

    class FakeSummarizer:
        def __init__(self) -> None:
            self.cost_tracker = FakeTracker()

        async def async_process_articles(
            self, articles: list[dict[str, object]]
        ) -> list[dict[str, object]]:
            return [
                {
                    **articles[0],
                    "summary": "Article summary",
                    "sentiment": "Neutral",
                }
            ]

    requested_limits: list[int] = []
    monkeypatch.setattr("builtins.input", lambda _: "1")
    monkeypatch.setattr(main_module, "NewsSummarizer", FakeSummarizer)
    monkeypatch.setattr(
        main_module,
        "fetch_tech_news",
        lambda limit: requested_limits.append(limit)
        or [
            {
                "title": "Headline",
                "source": {"name": "Example"},
            }
        ],
    )

    assert main_module.main() == 0

    output = capsys.readouterr().out
    assert requested_limits == [1]
    assert "Headline" in output
    assert "Article summary" in output
    assert "Neutral" in output
    assert "Usage summary" in output