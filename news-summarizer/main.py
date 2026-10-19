"""Interactive entry point for the technology news summarizer."""

from __future__ import annotations

from news_api import NewsAPIError
from summarizer import NewsSummarizer


def get_article_count() -> int | None:
    """Prompt for a valid article count, or return ``None`` to quit."""

    while True:
        raw_count = input(
            "How many technology articles should be processed? "
            "(1-5, or q to quit): "
        ).strip().lower()
        if raw_count in {"q", "quit", "exit"}:
            return None
        try:
            count = int(raw_count)
        except ValueError:
            print("Please enter a number from 1 to 5, or q to quit.")
            continue
        if 1 <= count <= 5:
            return count
        print("Please choose between 1 and 5 articles.")


def run_interactive() -> None:
    """Run the interactive news-fetching and analysis workflow."""

    print("Technology News Summarizer")
    print("OpenAI creates summaries; Cohere performs aspect-based sentiment analysis.\n")

    while True:
        count = get_article_count()
        if count is None:
            print("Goodbye.")
            return

        print(f"\nFetching and processing {count} article(s)...")
        summarizer = NewsSummarizer()
        try:
            analyses = summarizer.run(count=count)
        except NewsAPIError as exc:
            print(f"Could not fetch news: {exc}")
            continue

        if analyses:
            summarizer.display_results(analyses)
        else:
            print("No articles were processed successfully.")

        again = input("\nProcess another batch? (y/n): ").strip().lower()
        if again not in {"y", "yes"}:
            print("Goodbye.")
            return


def main() -> None:
    """Start the interactive application and handle terminal exits."""

    try:
        run_interactive()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")


if __name__ == "__main__":
    main()
