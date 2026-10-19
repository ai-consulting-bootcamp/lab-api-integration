"""Unit tests for the news summarizer workflow."""

#Tests cover:
#ABSA JSON parsing
#Markdown-fenced JSON
#Invalid response fallback
#Processing exactly two articles
#Mocked OpenAI and Cohere calls
#Cost tracking
#Displaying aspects and total cost

from __future__ import annotations

import summarizer
from llm_providers import ProviderResult
from news_api import NewsArticle


def article(title: str = "Technology headline") -> NewsArticle:
    """Create a deterministic article fixture."""

    return NewsArticle(
        title=title,
        source="Test Source",
        description="A test technology article.",
        url="https://example.com/article",
        published_at="2026-10-19T12:00:00Z",
    )


def provider_result(
    provider: str, text: str, cost: float = 0.001
) -> ProviderResult:
    """Create a deterministic provider response fixture."""

    return ProviderResult(
        provider=provider,
        model="test-model",
        text=text,
        input_tokens=10,
        output_tokens=5,
        cost_usd=cost,
    )


def test_parse_aspects_from_json() -> None:
    """ABSA JSON is normalized into aspect records."""

    response = (
        '{"aspects": [{"aspect": "Product", "sentiment": "Positive", '
        '"confidence": 0.9, "evidence": "Strong adoption"}]}'
    )

    result = summarizer._parse_aspects(response)

    assert result == [
        {
            "aspect": "Product",
            "sentiment": "Positive",
            "confidence": 0.9,
            "evidence": "Strong adoption",
        }
    ]


def test_parse_aspects_accepts_markdown_code_fence() -> None:
    """JSON wrapped in a markdown fence is still parsed."""

    result = summarizer._parse_aspects(
        '```json\n{"aspects": [{"aspect": "Security", "sentiment": "Negative"}]}\n```'
    )

    assert result[0]["aspect"] == "Security"
    assert result[0]["sentiment"] == "Negative"


def test_parse_aspects_falls_back_for_invalid_json() -> None:
    """Malformed model output does not crash the summarizer."""

    result = summarizer._parse_aspects("Positive because adoption increased")

    assert result == [
        {"aspect": "overall", "sentiment": "Positive because adoption increased"}
    ]


def test_run_processes_two_articles_and_tracks_costs(monkeypatch) -> None:
    """The workflow fetches two articles and records both provider calls."""

    articles = [article("First headline"), article("Second headline")]
    calls = {"fetch_count": None, "openai": 0, "cohere": 0}

    def fake_fetch(count: int) -> list[NewsArticle]:
        calls["fetch_count"] = count
        return articles

    def fake_openai(prompt: str) -> ProviderResult:
        calls["openai"] += 1
        return provider_result("openai", "A concise summary.", 0.002)

    def fake_cohere(prompt: str) -> ProviderResult:
        calls["cohere"] += 1
        return provider_result(
            "cohere",
            '{"aspects": [{"aspect": "Product", "sentiment": "Positive"}]}',
            0.003,
        )

    monkeypatch.setattr(summarizer, "fetch_tech_news", fake_fetch)
    monkeypatch.setattr(summarizer, "ask_openai", fake_openai)
    monkeypatch.setattr(summarizer, "ask_cohere", fake_cohere)

    workflow = summarizer.NewsSummarizer()
    results = workflow.run(count=2)

    assert calls == {"fetch_count": 2, "openai": 2, "cohere": 2}
    assert len(results) == 2
    assert results[0].aspects[0]["sentiment"] == "Positive"
    assert workflow.cost_tracker.total_cost_usd == 0.010


def test_display_results_shows_aspects_and_cost(capsys) -> None:
    """Displayed output includes ABSA details and the total cost."""

    workflow = summarizer.NewsSummarizer()
    workflow.cost_tracker.add(provider_result("cohere", "", 0.004))
    workflow.display_results(
        [
            summarizer.ArticleAnalysis(
                article=article(),
                summary="A concise summary.",
                aspects=[
                    {
                        "aspect": "Users",
                        "sentiment": "Neutral",
                        "confidence": 0.75,
                        "evidence": "No clear effect reported.",
                    }
                ],
            )
        ]
    )

    output = capsys.readouterr().out
    assert "Aspect-based sentiment:" in output
    assert "Users: Neutral" in output
    assert "Total estimated cost: $0.004000" in output
