"""Fetch news articles, summarize them, and analyze their sentiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from llm_providers import CostTracker, ProviderResult, ask_cohere, ask_openai
from news_api import NewsAPIError, NewsArticle, fetch_tech_news


@dataclass(frozen=True)
class ArticleAnalysis:
    """Summary and aspect-based sentiment analysis for one article."""

    article: NewsArticle
    summary: str
    aspects: list[dict[str, Any]]


def _parse_aspects(response_text: str) -> list[dict[str, Any]]:
    """Parse Cohere's JSON ABSA response, including fenced JSON output."""

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return [{"aspect": "overall", "sentiment": response_text.strip()}]

    raw_aspects = payload.get("aspects", []) if isinstance(payload, dict) else []
    if not isinstance(raw_aspects, list):
        return [{"aspect": "overall", "sentiment": "Unknown"}]

    aspects: list[dict[str, Any]] = []
    for item in raw_aspects:
        if not isinstance(item, dict) or not item.get("aspect"):
            continue
        aspects.append(
            {
                "aspect": str(item["aspect"]),
                "sentiment": str(item.get("sentiment", "Neutral")),
                "confidence": item.get("confidence"),
                "evidence": str(item.get("evidence", "")),
            }
        )
    return aspects or [{"aspect": "overall", "sentiment": "Neutral"}]


class NewsSummarizer:
    """Coordinate news retrieval, summarization, sentiment, and cost tracking."""

    def __init__(self) -> None:
        self.cost_tracker = CostTracker()

    def summarize_article(self, article: NewsArticle) -> ProviderResult:
        """Summarize one article with OpenAI and record its cost."""

        prompt = (
            "Summarize this technology news article in two concise sentences. "
            "Keep only the key facts and do not invent information.\n\n"
            f"Title: {article.title}\n"
            f"Description: {article.description}\n"
            f"Source: {article.source}"
        )
        result = ask_openai(prompt)
        self.cost_tracker.add(result)
        return result

    def analyze_aspects(
        self, article: NewsArticle, summary: str
    ) -> ProviderResult:
        """Analyze sentiment for each meaningful aspect with Cohere."""

        prompt = (
            "Perform aspect-based sentiment analysis (ABSA) on this technology "
            "news article. Identify meaningful aspects such as the product, "
            "company, security, users, or financial impact. Return ONLY valid "
            "JSON in this exact shape: {\"aspects\": [{\"aspect\": "
            "\"...\", \"sentiment\": \"Positive|Negative|Neutral\", "
            "\"confidence\": 0.0, \"evidence\": \"...\"}]}. "
            "Do not infer sentiment for aspects not supported by the text.\n\n"
            f"Title: {article.title}\n"
            f"Description: {article.description}\n"
            f"Summary: {summary}"
        )
        result = ask_cohere(prompt)
        self.cost_tracker.add(result)
        return result

    def analyze_sentiment(
        self, article: NewsArticle, summary: str
    ) -> ProviderResult:
        """Backward-compatible alias for the ABSA analysis method."""

        return self.analyze_aspects(article, summary)

    def process_article(self, article: NewsArticle) -> ArticleAnalysis:
        """Summarize and analyze sentiment for one article."""

        summary = self.summarize_article(article)
        sentiment = self.analyze_aspects(article, summary.text)
        return ArticleAnalysis(
            article=article,
            summary=summary.text,
            aspects=_parse_aspects(sentiment.text),
        )

    def run(self, count: int = 2) -> list[ArticleAnalysis]:
        """Fetch and process ``count`` technology articles."""

        articles = fetch_tech_news(count)
        analyses: list[ArticleAnalysis] = []
        for article in articles:
            try:
                analyses.append(self.process_article(article))
            except Exception as exc:  # provider SDKs expose different exception types
                print(f"Could not process '{article.title}': {exc}")
        return analyses

    def display_results(self, analyses: list[ArticleAnalysis]) -> None:
        """Print article analyses followed by the accumulated cost summary."""

        for index, analysis in enumerate(analyses, start=1):
            print(f"\n{index}. {analysis.article.title}")
            print(f"   Source: {analysis.article.source}")
            print(f"   Summary: {analysis.summary}")
            print("   Aspect-based sentiment:")
            for aspect in analysis.aspects:
                confidence = aspect.get("confidence")
                confidence_text = (
                    f", confidence={confidence}" if confidence is not None else ""
                )
                print(
                    f"      - {aspect['aspect']}: {aspect['sentiment']}"
                    f"{confidence_text}"
                )
                if aspect.get("evidence"):
                    print(f"        Evidence: {aspect['evidence']}")
        print(f"\n{self.cost_tracker.summary()}")


def main() -> None:
    """Fetch two articles, process them, and display the results."""

    try:
        summarizer = NewsSummarizer()
        analyses = summarizer.run(count=2)
        summarizer.display_results(analyses)
    except NewsAPIError as exc:
        print(f"Could not fetch news: {exc}")


if __name__ == "__main__":
    main()
