"""News -> summary -> sentiment workflow."""

import time

from config import Config, get_config
from llm_providers import CostTracker, CohereProvider, OpenAIProvider, ask_with_fallback
from news_api import NewsAPIClient


class NewsSummarizer:
    """Process articles while keeping provider failures recoverable."""

    def __init__(self, config: Config | None = None, news_client=None, summary_provider=None, sentiment_provider=None):
        self.config = config or get_config()
        self.news_client = news_client or NewsAPIClient(self.config)
        self.summary_provider = summary_provider or OpenAIProvider(self.config)
        self.sentiment_provider = sentiment_provider or CohereProvider(self.config)
        self.tracker = CostTracker(self.config.daily_budget)

    def process_article(self, article: dict) -> dict:
        """Create a summary and classify its sentiment."""
        source = article.get("content") or article.get("description") or article.get("title", "")
        summary_prompt = f"Summarize this news article in 60 words or fewer:\n{source}"
        summary = ask_with_fallback(summary_prompt, self.summary_provider, self.sentiment_provider, self.tracker, self.config.max_retries)
        sentiment_prompt = f"Classify the sentiment as exactly positive, negative, or neutral.\nSummary: {summary.text}"
        sentiment = ask_with_fallback(sentiment_prompt, self.sentiment_provider, self.summary_provider, self.tracker, self.config.max_retries)
        return {
            "title": article.get("title", "Untitled"),
            "summary": summary.text,
            "sentiment": sentiment.text.lower().split()[0],
            "summary_provider": summary.provider,
            "sentiment_provider": sentiment.provider,
            "cost": round(summary.cost + sentiment.cost, 6),
        }

    def run(self, category: str = "technology", limit: int = 2) -> list[dict]:
        """Fetch and process up to `limit` articles with a small rate-limit pause."""
        articles = self.news_client.top_headlines(category=category, page_size=limit)
        results = []
        for index, article in enumerate(articles[:limit]):
            if index:
                time.sleep(0.2)
            results.append(self.process_article(article))
        return results


if __name__ == "__main__":
    summarizer = NewsSummarizer()
    for result in summarizer.run():
        print(f"\n{result['title']}\n{result['summary']}\nSentiment: {result['sentiment']}")
    print(f"\nCost: {summarizer.tracker.summary()}")
