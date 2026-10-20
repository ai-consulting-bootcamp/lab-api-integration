
from datetime import datetime, timezone

from news_api import NewsAPI
from llm_providers import LLMProviders


class NewsSummarizer:
    """Coordinate news retrieval, summarization, and sentiment analysis."""

    def __init__(self):
        self.news_api = NewsAPI()
        self.providers = LLMProviders()

    def process_article(self, article):
        """Summarize one article and analyze its sentiment."""

        title = article.get("title") or "Untitled"
        description = article.get("description") or ""
        content = article.get("content") or ""

        # NewsAPI may provide truncated article content.
        article_text = "\n".join(
            part for part in [title, description, content] if part
        )

        if not article_text.strip():
            raise ValueError("Article contains no usable text.")

        # Record spending before processing.
        cost_before = self.providers.total_cost

        # OpenAI first, Cohere fallback.
        summary_result = self.providers.summarize(article_text)
        summary = summary_result["summary"]

        # Cohere first, OpenAI fallback.
        sentiment_result = self.providers.analyze_sentiment(summary)

        # Include all provider costs incurred for this article.
        article_cost = self.providers.total_cost - cost_before

        return {
            "title": title,
            "source": (article.get("source") or {}).get(
                "name", "Unknown"
            ),
            "url": article.get("url", ""),
            "summary": summary,
            "sentiment": sentiment_result["sentiment"],
            "cost": article_cost,
            "processed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def process_news(
        self,
        category="technology",
        country="us",
        limit=2,
    ):
        """Fetch and process multiple news articles."""

        if limit < 1:
            raise ValueError("Article limit must be at least 1.")

        articles = self.news_api.get_top_headlines(
            category=category,
            country=country,
            page_size=limit,
        )

        if not articles:
            print("No articles available.")
            return []

        results = []

        for index, article in enumerate(articles, start=1):
            print(f"\nProcessing article {index}/{len(articles)}...")

            try:
                result = self.process_article(article)
                results.append(result)

                print(f"Completed: {result['title']}")

            except Exception as error:
                print(
                    f"Failed to process article {index}: "
                    f"{type(error).__name__}: {error}"
                )

                # Stop if the spending limit has been reached.
                self.providers.check_budget()

        return results

    def print_results(self, results):
        """Display processed articles and estimated API costs."""

        print("\n" + "=" * 60)
        print("NEWS SUMMARIZER RESULTS")
        print("=" * 60)

        for index, result in enumerate(results, start=1):
            print(f"\nARTICLE {index}")
            print(f"Title: {result['title']}")
            print(f"Source: {result['source']}")
            print(f"URL: {result['url']}")

            print("\nSummary:")
            print(result["summary"])

            print("\nSentiment:")
            print(result["sentiment"])

            print(f"\nArticle cost: ${result['cost']:.6f}")
            print("-" * 60)

        print("\nCOST SUMMARY")
        print(f"Articles processed: {len(results)}")
        print(
            f"Total API cost: "
            f"${self.providers.total_cost:.6f}"
        )
        print(
            f"Configured budget: "
            f"${self.providers.config.daily_budget:.2f}"
        )


if __name__ == "__main__":
    summarizer = NewsSummarizer()

    print("Fetching technology news...")

    results = summarizer.process_news(
        category="technology",
        country="us",
        limit=2,
    )

    summarizer.print_results(results)
