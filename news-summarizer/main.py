"""Interactive command-line application for the technology news summarizer."""

import asyncio
import sys

from news_api import fetch_tech_news
from summarizer import NewsSummarizer


DEFAULT_ARTICLE_LIMIT = 3
MAX_ARTICLE_LIMIT = 5


def prompt_article_limit() -> int | None:
    """Ask how many articles to process; return None when the user exits."""
    while True:
        try:
            answer = input(
                f"How many technology articles should I summarize? "
                f"(1-{MAX_ARTICLE_LIMIT}, default {DEFAULT_ARTICLE_LIMIT}; "
                "q to quit): "
            ).strip()
        except EOFError:
            print()
            return None

        if answer.lower() in {"q", "quit"}:
            return None
        if not answer:
            return DEFAULT_ARTICLE_LIMIT

        try:
            limit = int(answer)
        except ValueError:
            print("Enter a whole number or q to quit.")
            continue

        if 1 <= limit <= MAX_ARTICLE_LIMIT:
            return limit
        print(f"Choose a number between 1 and {MAX_ARTICLE_LIMIT}.")


def display_results(articles: list[dict[str, object]]) -> None:
    """Print processed article details."""
    if not articles:
        print("No technology articles were returned.")
        return

    for number, article in enumerate(articles, start=1):
        source = article.get("source") or {}
        source_name = (
            source.get("name", "Unknown") if isinstance(source, dict) else "Unknown"
        )
        print(f"\n{number}. {article.get('title') or 'Untitled'}")
        print(f"   Source: {source_name}")
        print(f"   Summary: {article.get('summary', 'Unavailable')}")
        print(f"   Sentiment: {article.get('sentiment', 'Unavailable')}")
        print(f"   URL: {article.get('url') or 'Unavailable'}")


def main() -> int:
    """Prompt for a batch size, process articles, and report provider costs."""
    try:
        limit = prompt_article_limit()
        if limit is None:
            print("No articles processed.")
            return 0

        summarizer = NewsSummarizer()
        articles = fetch_tech_news(limit=limit)
        results = asyncio.run(summarizer.async_process_articles(articles))
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    display_results(results)
    print("\n" + summarizer.cost_tracker.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())