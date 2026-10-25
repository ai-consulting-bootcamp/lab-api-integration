from summarizer import process_articles


def main():
    """Run the news summarizer and display the results."""
    try:
        results = process_articles(limit=3)

        if not results:
            print("No articles were processed.")
            return

        for number, article in enumerate(results, start=1):
            print(f"\n--- Article {number} ---")
            print(f"Title: {article['title']}")
            print(f"Source: {article['source']}")
            print(f"Summary: {article['summary']}")
            print(f"Sentiment: {article['sentiment']}")
            print(f"Sentiment provider: {article['sentiment_provider']}")
            print(f"URL: {article['url']}")

        total_input = sum(item["input_tokens"] for item in results)
        total_output = sum(item["output_tokens"] for item in results)

        print("\n--- Token usage for summaries ---")
        print(f"Input tokens: {total_input}")
        print(f"Output tokens: {total_output}")

    except Exception as error:
        print(f"The program could not finish: {error}")


if __name__ == "__main__":
    main()