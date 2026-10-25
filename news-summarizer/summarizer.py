
from news_api import fetch_articles
from llm_providers import LLMProviders
from analytics import trending_topics
import time


class NewsSummarizer:
    def __init__(self):
        self.providers = LLMProviders()

    def run(self):
        articles = fetch_articles(limit=10)

        if not articles:
            print("No news articles were returned.")
            return

        processed_articles = []

        for index, article in enumerate(articles):
            if index:
                time.sleep(0.2)  # Small client-side delay to respect provider limits.
            title = article.get("title") or "Untitled"
            description = article.get("description") or title

            print(f"\nTitle: {title}")

            try:
                summary = self.providers.summarize(description)
                sentiment = self.providers.analyze_sentiment(summary)

                article["summary"] = summary
                article["sentiment"] = sentiment
                processed_articles.append(article)

                print(f"Summary: {summary}")
                print(f"Sentiment: {sentiment}")

            except Exception as error:
                print(f"Processing failed: {error}")
                # Preserve the article in the output when one provider fails.
                article["summary"] = description
                article["sentiment"] = "unavailable"
                processed_articles.append(article)

        print("\n=== Trending Topics ===")
        topics = trending_topics(processed_articles)

        if topics:
            for topic, count in topics:
                print(f"{topic}: mentioned {count} times")
        else:
            print("No trending topics identified.")

        try:
            cost = f"${float(self.providers.total_cost):.6f}"
        except (TypeError, ValueError):
            cost = "unavailable"

        print(f"\nEstimated total provider cost: {cost}")


if __name__ == "__main__":
    NewsSummarizer().run()
