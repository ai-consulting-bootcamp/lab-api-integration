from news_api import fetch_tech_news
from llm_providers import (
    analyze_sentiment_with_fallback,
    summarize_with_openai,
)


def process_articles(limit=2):
    """Fetch news articles, summarize them, and analyze sentiment."""
    articles = fetch_tech_news()
    results = []

    for article in articles[:limit]:
        title = article.get("title") or "No title"
        description = article.get("description") or ""
        content = article.get("content") or ""
        article_text = content or description

        if not article_text.strip():
            print(f"Skipping article because it has no text: {title}")
            continue

        summary_result = summarize_with_openai(article_text)
        sentiment_result = analyze_sentiment_with_fallback(article_text)

        result = {
            "title": title,
            "source": article.get("source", {}).get("name", "Unknown"),
            "url": article.get("url", ""),
            "summary": summary_result["text"],
            "sentiment": sentiment_result["sentiment"],
            "sentiment_provider": sentiment_result["provider"],
            "input_tokens": summary_result["input_tokens"],
            "output_tokens": summary_result["output_tokens"],
        }
        results.append(result)

    return results


if __name__ == "__main__":
    results = process_articles(limit=2)

    total_input_tokens = 0
    total_output_tokens = 0

    for item in results:
        print(f"\nTitle: {item['title']}")
        print(f"Source: {item['source']}")
        print(f"Summary: {item['summary']}")
        print(f"Sentiment: {item['sentiment']}")
        print(f"Sentiment provider: {item['sentiment_provider']}")
        print(f"URL: {item['url']}")

        total_input_tokens += item["input_tokens"]
        total_output_tokens += item["output_tokens"]

    print("\nToken usage for summaries:")
    print(f"Input tokens: {total_input_tokens}")
    print(f"Output tokens: {total_output_tokens}")