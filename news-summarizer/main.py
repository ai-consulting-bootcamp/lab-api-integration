"""Run the news summarizer interactively or as a single batch.

Examples:
    python main.py
    python main.py --category science --count 3
"""

import argparse

from llm_providers import LLMError
from news_api import NewsAPIError
from summarizer import ArticleResult, NewsSummarizer

# Supported News API headline categories.
CATEGORIES = (
    "business", "entertainment", "general", "health",
    "science", "sports", "technology",
)
DEFAULT_CATEGORY = "technology"
DEFAULT_COUNT = 3
MAX_COUNT = 5  # Limit the number of articles and associated LLM costs.
QUIT_COMMANDS = {"q", "quit", "exit"}


def print_result(number: int, result: ArticleResult) -> None:
    """Display an article's summary, sentiment, and processing cost."""
    print(f"\n{number}. {result.title}")
    print(f"   Source:    {result.source}")
    print(f"   Link:      {result.url}")
    print(f"   Summary:   {result.summary}  [{result.summary_provider}]")
    print(
        f"   Sentiment: {result.sentiment} - {result.sentiment_reason}"
        f"  [{result.sentiment_provider}]"
    )
    fallback_note = "  (fallback used)" if result.used_fallback else ""
    print(f"   Cost:      ${result.cost:.6f}{fallback_note}")


def process_batch(summarizer: NewsSummarizer, category: str, count: int) -> None:
    """Process a batch and display the results and accumulated costs."""
    print(f"\nFetching {count} {category} articles...")
    try:
        results = summarizer.run(category=category, count=count)
    except NewsAPIError as error:
        print(f"❌ Could not fetch news: {error}")
        return
    except LLMError as error:
        print(f"❌ {error}")
        return

    if not results:
        print("❌ No articles were processed")
        return

    for number, result in enumerate(results, start=1):
        print_result(number, result)

    print(f"\n{summarizer.llm.costs.summary()}")


def ask_category() -> str | None:
    """Prompt for a valid category, or return None when quitting."""
    while True:
        answer = input(
            f"\nCategory [{DEFAULT_CATEGORY}] "
            f"({', '.join(CATEGORIES)}), or 'q' to quit: "
        ).strip().lower()

        if answer in QUIT_COMMANDS:
            return None
        if not answer:
            return DEFAULT_CATEGORY
        if answer in CATEGORIES:
            return answer
        print(f"Unknown category '{answer}'. Choose one from the list.")


def ask_count() -> int:
    """Prompt for an article count within the allowed range."""
    while True:
        answer = input(
            f"How many articles? [1-{MAX_COUNT}, default {DEFAULT_COUNT}]: "
        ).strip()

        if not answer:
            return DEFAULT_COUNT
        if answer.isdigit() and 1 <= int(answer) <= MAX_COUNT:
            return int(answer)
        print(f"Please enter a number from 1 to {MAX_COUNT}.")


def interactive_loop(summarizer: NewsSummarizer) -> None:
    """Run batches until the user quits or interrupts input."""
    print("📰 Multi-Provider News Summarizer")
    print("   OpenAI writes the summary, Cohere rates the sentiment.")

    try:
        while True:
            category = ask_category()
            if category is None:
                break
            process_batch(summarizer, category, ask_count())
    except (EOFError, KeyboardInterrupt):
        # Exit gracefully when input closes or the user presses Ctrl+C.
        print()

    print("Goodbye!")


def parse_args() -> argparse.Namespace:
    """Parse optional arguments for single-batch execution."""
    parser = argparse.ArgumentParser(
        description="Summarize news with two LLM providers."
    )
    parser.add_argument(
        "--category", choices=CATEGORIES,
        help="process one batch of this category and exit",
    )
    parser.add_argument(
        "--count", type=int, choices=range(1, MAX_COUNT + 1),
        metavar=f"1-{MAX_COUNT}",
        help=f"how many articles (default {DEFAULT_COUNT})",
    )
    return parser.parse_args()


def main() -> None:
    """Start interactive mode or process one command-line batch."""
    args = parse_args()
    try:
        summarizer = NewsSummarizer()
    except ValueError as error:
        # Report missing or invalid API configuration before starting.
        print(f"❌ {error}")
        raise SystemExit(1) from error

    if args.category or args.count:
        process_batch(
            summarizer,
            args.category or DEFAULT_CATEGORY,
            args.count or DEFAULT_COUNT,
        )
    else:
        interactive_loop(summarizer)


if __name__ == "__main__":
    main()
