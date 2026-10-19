"""Connect article retrieval, summaries, sentiment, and token tracking."""

from news_api import fetch_articles
from llm_providers import summarize_text, analyze_sentiment


def summarize_articles(topic, articles=None):
    # Supplying articles allows reuse of saved data without a NewsAPI request.
    if articles is None:
        articles = fetch_articles(topic)

    results = []
    usage = {
        "openai": {"input_tokens": 0, "output_tokens": 0},
        "cohere": {"input_tokens": 0, "output_tokens": 0},
    }

    for article in articles:
        # NewsAPI fields can be missing or None. Only join nonempty text.
        parts = [
            article.get("title"),
            article.get("description"),
            article.get("content"),
        ]
        text = "\n\n".join(part for part in parts if part and part.strip())
        if not text.strip():
            continue

        summary = summarize_text(text)
        sentiment = analyze_sentiment(text)

        results.append({
            "title": article.get("title"),
            "url": article.get("url"),
            "summary": summary["text"],
            "sentiment": sentiment["text"],
            "usage": {"openai": summary, "cohere": sentiment},
        })

        for provider, response in (("openai", summary), ("cohere", sentiment)):
            usage[provider]["input_tokens"] += response["input_tokens"]
            usage[provider]["output_tokens"] += response["output_tokens"]

    return {"articles": results, "usage": usage}


if __name__ == "__main__":
    result = summarize_articles('"artificial intelligence"')

    for article in result["articles"]:
        print("\nTitel:", article["title"])
        print("Zusammenfassung:", article["summary"])
        print("Stimmung:", article["sentiment"])
        print("-" * 60)

    print("\nTOKENVERBRAUCH")
    for provider, tokens in result["usage"].items():
        total = tokens["input_tokens"] + tokens["output_tokens"]

        print(f"\n{provider.upper()}:")
        print("  Input:", tokens["input_tokens"])
        print("  Output:", tokens["output_tokens"])
        print("  Gesamt:", total)