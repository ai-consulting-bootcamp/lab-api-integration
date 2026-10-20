
from news_api import fetch_news
from summarizer import summarize_with_fallback, analyze_sentiment


def main():
    """Run the multi-provider news summarizer."""

    print("\n=== Multi-Provider News Summarizer ===\n")

    try:
        count = int(input("How many articles? (1-5): "))
    except ValueError:
        print("Invalid number.")
        return

    if not 1 <= count <= 5:
        print("Please choose between 1 and 5.")
        return

    articles = fetch_news(limit=count)

    print(f"\nFetched {len(articles)} articles.")

    for index, article in enumerate(articles, start=1):
        print(f"\n{'=' * 50}")
        print(f"ARTICLE {index}")
        print(f"{'=' * 50}")

        print("Title:", article.get("title"))

        try:
            summary = summarize_with_fallback(article)
            sentiment = analyze_sentiment(summary)

            print("\nSummary:", summary)
            print("Sentiment:", sentiment)
            print("Source:", article.get("url"))

        except Exception as error:
            print(f"Failed to process article: {error}")

    print("\nProcessing completed!")


if __name__ == "__main__":
    main()
