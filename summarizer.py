"""
summarizer.py - News Summarizer core logic.

- get_weather_advice(): fetch external data, then put it into the prompt
- generate_and_review(): Step 1 OpenAI output -> Step 2 passed to Cohere
"""

from typing import Any, Dict, List, Optional

from llm_providers import LLMProviders, TokenBudgetManager, config
from news_api import fetch_news


class NewsSummarizer:
    """Summarize news articles with OpenAI and analyze sentiment with Cohere."""

    def __init__(self, budget_manager: Optional[TokenBudgetManager] = None,
                 providers: Optional[LLMProviders] = None):
        """
        Args:
            budget_manager: Shared TokenBudgetManager (from Config if not given)
            providers: LLMProviders instance (created if not given)
        """
        self.budget_manager = budget_manager or config.get_budget_manager()
        self.providers = providers or LLMProviders(budget_manager=self.budget_manager)

    def summarize(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 1: Summarize an article (OpenAI primary, Cohere fallback).

        Args:
            article: Article dictionary from fetch_news()

        Returns:
            Provider result with the summary in "response"
        """
        # Create prompt with the external data (like get_weather_advice)
        prompt = f"""Based on this news article:

Title: {article['title']}
Source: {article['source']}
Description: {article['description']}
Content: {article['content']}

Summarize the article in 2-3 sentences. Use only the information above."""

        return self.providers.ask_with_fallback(prompt, primary="openai", secondary="cohere")

    def analyze_sentiment(self, summary: str) -> Dict[str, Any]:
        """
        Step 2: Analyze the sentiment of the summary (Cohere primary, OpenAI fallback).

        Args:
            summary: Summary text produced in Step 1

        Returns:
            Provider result with the sentiment analysis in "response"
        """
        # Pass the OpenAI output to Cohere (like generate_and_review)
        prompt = f"""Analyze the sentiment of this news summary:

{summary}

Provide:
1. Sentiment: positive, negative or neutral
2. A one-sentence reason"""

        return self.providers.ask_with_fallback(prompt, primary="cohere", secondary="openai")

    def process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Step 1 and Step 2 for one article.

        Args:
            article: Article dictionary from fetch_news()

        Returns:
            Dictionary with article, summary, sentiment, providers and usage data
        """
        print(f"\nStep 1: Summarizing '{article['title']}'...")
        summary_result = self.summarize(article)

        print("\nStep 2: Analyzing sentiment...")
        sentiment_result = self.analyze_sentiment(summary_result["response"])

        return {
            "article": article,
            "summary": summary_result["response"],
            "sentiment": sentiment_result["response"],
            "providers": {
                "summary": summary_result["provider"],
                "sentiment": sentiment_result["provider"]
            },
            "fallback_used": summary_result["fallback_used"] or sentiment_result["fallback_used"],
            "usage": {
                "summary": summary_result["usage"],
                "sentiment": sentiment_result["usage"]
            }
        }

    def process_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process several articles. A failed article is logged and skipped;
        processing stops when the daily budget is used up.

        Args:
            articles: List of article dictionaries

        Returns:
            List of processed article dictionaries
        """
        results = []
        for i, article in enumerate(articles, 1):
            if self.budget_manager.used_budget >= self.budget_manager.daily_budget:
                print("\n⛔ Daily budget used up - stopping.")
                break

            print(f"\n{'=' * 60}\nArticle {i}/{len(articles)}\n{'=' * 60}")
            try:
                results.append(self.process_article(article))
            except Exception as e:
                print(f"❌ Failed to process article: {e}")
        return results


if __name__ == "__main__":
    # Checkpoint 4: 2 articles, OpenAI summary, Cohere sentiment, cost summary
    config.validate()
    summarizer = NewsSummarizer()
    articles = fetch_news(category="technology", page_size=2)
    results = summarizer.process_articles(articles)

    for result in results:
        print(f"\n📰 {result['article']['title']}")
        print(f"📝 Summary ({result['providers']['summary']}): {result['summary']}")
        print(f"🎭 Sentiment ({result['providers']['sentiment']}): {result['sentiment']}")

    summarizer.budget_manager.print_summary()
