from summarizer import NewsSummarizer


def main():
    """Run the interactive news summarizer application."""

    print("\n=== Multi-Provider News Summarizer ===")

    # Get user input
    user_input = input(
        "How many articles would you like to process? (1-3, default 2): "
    ).strip()

    # Validate input
    if user_input and user_input not in ["1", "2", "3"]:
        print("Invalid input. Please enter 1, 2, or 3.")
        return

    article_count = int(user_input) if user_input else 2

    print(f"Selected number of articles: {article_count}")
    # Initialize summarizer and handle potential errors
    try:
        summarizer = NewsSummarizer()
        results = summarizer.process_articles(limit=article_count)

    except Exception as e:
        print(f"Error processing news articles: {e}")
        print("Please check your API connection and try again.")
        return

    # Check if any articles were returned
    if not results:
        print("No news articles were found.")
        print("Please try again later.")
        return

    # Display processed articles
    for index, article in enumerate(results, start=1):
        print(f"\n{'=' * 60}")
        print(f"ARTICLE {index}")
        print(f"{'=' * 60}")

        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print(f"URL: {article['url']}")

        print(f"\nSummary:\n{article['summary']}")
        print(f"\nSentiment:\n{article['sentiment']}")

    # Display cost summary
    budget_summary = summarizer.llm.budget_manager.get_summary()

    print(f"\n{'=' * 60}")
    print("COST SUMMARY")
    print(f"{'=' * 60}")

    print(f"Daily budget: ${budget_summary['daily_budget']:.2f}")
    print(f"Total cost: ${budget_summary['used_budget']:.6f}")
    print(f"Remaining budget: ${budget_summary['remaining_budget']:.6f}")

    # Display costs per provider
    for provider, usage in budget_summary["provider_usage"].items():
        print(f"\n{provider.upper()}:")
        print(f"Input tokens: {usage['input_tokens']}")
        print(f"Output tokens: {usage['output_tokens']}")
        print(f"Cost: ${usage['cost']:.6f}")


if __name__ == "__main__":
    main()