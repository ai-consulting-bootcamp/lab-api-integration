"""Orchestrate AskNews retrieval, summary, and sentiment analysis."""

from llm_providers import LLMProviders
from news_api import NewsFetchError, fetch_news

class WorkflowError(RuntimeError):
    """Raised when a workflow stage fails with an actionable message."""

class NewsSummarizer:
    """Run the end-to-end news summarization workflow."""

    def __init__(self) -> None:
        self.providers = LLMProviders()

    def process_news(self, query: str, articles: int = 2) -> dict:
        """Fetch news, summarize it, and classify summary sentiment."""
        try:
            news_context = fetch_news(query, articles=articles)
        except (ValueError, NewsFetchError) as error:
            raise WorkflowError(str(error)) from error
        if not news_context.strip():
            raise ValueError("AskNews returned empty news context.")

        summary = self.providers.summarize(news_context)
        if not summary.strip():
            raise ValueError("The summarization provider returned an empty summary.")

        sentiment = self.providers.analyze_sentiment(summary)

        return {
            "query": query,
            "summary": summary,
            "sentiment": sentiment,
            "cost": self.providers.get_cost_summary(),
        }


if __name__ == "__main__":
    summarizer = NewsSummarizer()
    result = summarizer.process_news(
        "Effect of Fed policy on the tech sector",
        articles=2,
    )

    print("\n=== News Summary ===")
    print("Query:", result["query"])
    print("Summary:", result["summary"])
    print("Sentiment:", result["sentiment"])
    print("Cost:", result["cost"])