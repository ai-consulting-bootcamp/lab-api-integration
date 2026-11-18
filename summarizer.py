"""Summarizer: fetches news, summarizes with OpenAI, and analyzes
sentiment with Cohere, each with fallback to the other provider."""
from datetime import datetime, timezone

from llm_providers import (
    BudgetExceededError,
    CohereProvider,
    CostTracker,
    OpenAIProvider,
    ProviderWithFallback,
)
from news_api import NewsAPI

VALID_SENTIMENTS = {"positive", "negative", "neutral"}


class NewsSummarizer:
    """Runs the full pipeline: fetch -> summarize -> sentiment -> record."""

    def __init__(self, news_api=None, cost_tracker=None,
                 summary_provider=None, sentiment_provider=None):
        """Real services by default; pass fakes in for testing."""
        self.cost_tracker = cost_tracker or CostTracker()
        self.news_api = news_api or NewsAPI()
        self.last_articles = []  # input payloads from the latest run, for tracing

        if summary_provider is None or sentiment_provider is None:
            openai_provider = OpenAIProvider(self.cost_tracker)
            cohere_provider = CohereProvider(self.cost_tracker)

        # Summaries: OpenAI first. Sentiment: Cohere first.
        self.summary_provider = summary_provider or ProviderWithFallback(
            openai_provider, cohere_provider
        )
        self.sentiment_provider = sentiment_provider or ProviderWithFallback(
            cohere_provider, openai_provider
        )

    @staticmethod
    def build_article_text(article):
        """Combine whatever text the article has; the title is always present."""
        parts = [
            article.get("title", ""),
            article.get("description", ""),
            article.get("content", ""),
        ]
        return " ".join(part for part in parts if part).strip()

    def summarize(self, article):
        """Return (summary, provider_name)."""
        prompt = (
            "Summarize this news article in 2-3 sentences. "
            "Use only information in the text. "
            "If the text is very short, summarize only what is there. "
            "Article: " + self.build_article_text(article)
        )
        return self.summary_provider.complete(prompt, max_tokens=150)

    @staticmethod
    def parse_sentiment(text):
        """Turn 'positive - reason' into ('positive', 'reason').

        If the model ignores the format, the label becomes 'unknown'
        so bad output is visible instead of silently wrong.
        """
        label_part, _, reason = text.partition("-")
        label = label_part.strip().strip("*.:").lower()
        if label not in VALID_SENTIMENTS:
            return "unknown", text.strip()
        return label, reason.strip()

    def analyze_sentiment(self, summary):
        """Return (label, reason, provider_name)."""
        prompt = (
            "Classify the sentiment of this news summary as exactly one of: "
            "positive, negative, neutral. "
            "Reply in this format: <label> - <one sentence reason>. "
            "Summary: " + summary
        )
        text, provider = self.sentiment_provider.complete(prompt, max_tokens=60)
        label, reason = self.parse_sentiment(text)
        return label, reason, provider

    def process_article(self, article):
        """Run one article through the pipeline and return the output record."""
        summary, summary_provider = self.summarize(article)
        sentiment, reason, sentiment_provider = self.analyze_sentiment(summary)
        return {
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "url": article.get("url", ""),
            "summary": summary,
            "sentiment": sentiment,
            "sentiment_reason": reason,
            "summary_provider": summary_provider,
            "sentiment_provider": sentiment_provider,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    def process_articles(self, category="technology", max_articles=3):
        """Fetch and process articles; one failure skips that article only."""
        articles = self.news_api.fetch_top_headlines(
            category=category, max_articles=max_articles
        )
        self.last_articles = articles
        results = []
        for i, article in enumerate(articles, 1):
            print(f"Processing {i}/{len(articles)}: {article['title'][:70]}")
            try:
                results.append(self.process_article(article))
            except BudgetExceededError as error:
                print(f"  ✗ {error}. Stopping.")
                break
            except Exception as error:  # noqa: BLE001
                print(f"  ✗ Skipped this article: {error}")
        return results


if __name__ == "__main__":
    summarizer = NewsSummarizer()
    results = summarizer.process_articles(max_articles=2)

    for record in results:
        print()
        print(f"📰 {record['title']}")
        print(f"   Summary ({record['summary_provider']}): {record['summary']}")
        print(f"   Sentiment ({record['sentiment_provider']}): "
              f"{record['sentiment']} - {record['sentiment_reason']}")

    stats = summarizer.cost_tracker.summary()
    print()
    print("Cost summary:")
    print(f"  Requests:         {stats['total_requests']}")
    print(f"  Total cost:       ${stats['total_cost']:.6f}")
    print(f"  Budget remaining: ${stats['budget_remaining']:.4f}")