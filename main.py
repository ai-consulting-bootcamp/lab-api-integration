"""Command-line entry point for the news summarizer."""

from rate_limit import LocalRateLimitError

import logging

from summarizer import NewsSummarizer, WorkflowError
from llm_providers import ProviderFailoverError

from budget import BudgetExceededError

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)


def main() -> None:
    """Run the interactive news summarizer."""
    query = input("What news topic should I summarize? ").strip()
    if not query:
        print("Please enter a search topic.")
        return

    raw_count = input("How many articles? (1-5, default 3): ").strip()
    try:
        articles = int(raw_count) if raw_count else 3
    except ValueError:
        print("Please enter a whole number.")
        return

    if not 1 <= articles <= 5:
        print("Choose a number between 1 and 5.")
        return

    try:
        result = NewsSummarizer().process_news(query, articles=articles)
    except (
        WorkflowError,
        ProviderFailoverError,
        LocalRateLimitError,
        BudgetExceededError,
        ) as error:
        print(f"Workflow could not complete: {error}")
        return
    except Exception:
        logging.exception("Unexpected workflow error")
        print("An unexpected error occurred. Check the application log.")
        return

    print("\n=== News Summary ===")
    print("Query:", result["query"])
    print("Summary:", result["summary"])
    print("Sentiment:", result["sentiment"])
    print("Cost:", result["cost"])


if __name__ == "__main__":
    main()