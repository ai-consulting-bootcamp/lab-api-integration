"""Interactive entry point for the multi-provider news summarizer."""
import json
from datetime import datetime
from pathlib import Path

from config import Config
from summarizer import NewsSummarizer

CATEGORIES = [
    "business", "entertainment", "general", "health",
    "science", "sports", "technology",
]
OUTPUT_DIR = Path("output")


def ask_category():
    """Ask for a News API category; default to technology."""
    print("Categories: " + ", ".join(CATEGORIES))
    choice = input("Category [technology]: ").strip().lower()
    if not choice:
        return "technology"
    if choice not in CATEGORIES:
        print("Unknown category, using technology.")
        return "technology"
    return choice


def ask_article_count():
    """Ask how many articles to process (1-5); default to 3."""
    choice = input("How many articles (1-5) [3]: ").strip()
    if not choice:
        return 3
    if choice.isdigit() and 1 <= int(choice) <= 5:
        return int(choice)
    print("Invalid number, using 3.")
    return 3


def print_results(results):
    """Show each output record in a readable format."""
    for record in results:
        print()
        print(f"📰 {record['title']}")
        print(f"   Source: {record['source']}")
        print(f"   Summary ({record['summary_provider']}): {record['summary']}")
        print(f"   Sentiment ({record['sentiment_provider']}): "
              f"{record['sentiment']} - {record['sentiment_reason']}")


def print_costs(stats):
    """Show the running cost totals."""
    print()
    print("💰 Cost summary (this session):")
    print(f"   Requests:         {stats['total_requests']}")
    print(f"   Total cost:       ${stats['total_cost']:.6f}")
    print(f"   Budget remaining: ${stats['budget_remaining']:.4f}")


def save_run(category, articles, results, stats):
    """Save inputs, outputs, and costs of one run to output/run_<time>.json."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"run_{timestamp}.json"
    run = {
        "run_at": datetime.now().isoformat(),
        "category": category,
        "models": {
            "summary": Config.OPENAI_MODEL,
            "sentiment": Config.COHERE_MODEL,
        },
        "input_articles": articles,
        "output_records": results,
        "cost_summary": stats,
    }
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False))
    return path


def main():
    """Run the interactive loop until the user quits."""
    print("=" * 60)
    print("Multi-Provider News Summarizer (OpenAI + Cohere)")
    print("=" * 60)

    try:
        Config.validate()
    except ValueError as error:
        print(f"✗ {error}")
        return

    summarizer = NewsSummarizer()

    while True:
        category = ask_category()
        count = ask_article_count()
        print()

        results = summarizer.process_articles(category=category, max_articles=count)

        if results:
            print_results(results)
            path = save_run(
                category,
                summarizer.last_articles,
                results,
                summarizer.cost_tracker.summary(),
            )
            print()
            print(f"💾 Run saved to {path}")
        else:
            print("No articles were processed.")

        print_costs(summarizer.cost_tracker.summary())
        print()
        if input("Run again? (y/n) [n]: ").strip().lower() != "y":
            break

    print("Goodbye!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("Stopped by user.")