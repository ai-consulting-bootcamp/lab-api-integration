"""
main.py - Interactive News Summarizer application 
Each run saves the input articles and output records to output/run_<timestamp>.json
for lab_proof.md.
"""

import argparse
import json
import os
from datetime import datetime

from llm_providers import config
from news_api import fetch_news
from summarizer import NewsSummarizer

CATEGORIES = ["business", "entertainment", "general", "health", "science", "sports", "technology"]


def ask_user():
    """Ask for category and number of articles."""
    print(f"Categories: {', '.join(CATEGORIES)}")
    category = input("Category [technology]: ").strip().lower() or "technology"
    if category not in CATEGORIES:
        print("Unknown category, using technology")
        category = "technology"

    count = input("Number of articles 1-5 [3]: ").strip() or "3"
    count = int(count) if count.isdigit() else 3
    return category, max(1, min(count, 5))


def save_results(results, budget_summary):
    """Save the run to output/run_<timestamp>.json and return the path."""
    os.makedirs("output", exist_ok=True)
    path = f"output/run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"results": results, "budget_summary": budget_summary}, f,
                  indent=2, ensure_ascii=False)
    return path


def main():
    """Fetch news, summarize with OpenAI, analyze sentiment with Cohere, show costs."""
    parser = argparse.ArgumentParser(description="Multi-Provider News Summarizer")
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--count", type=int, choices=range(1, 6))
    args = parser.parse_args()

    print("=" * 60)
    print("📰 MULTI-PROVIDER NEWS SUMMARIZER")
    print("   OpenAI = summary | Cohere = sentiment")
    print("=" * 60)

    try:
        config.validate()
    except ValueError as e:
        print(f"❌ {e}")
        return

    if args.category and args.count:
        category, count = args.category, args.count
    else:
        category, count = ask_user()

    articles = fetch_news(category=category, page_size=count)
    if not articles:
        print("No articles found. Check your News API key or try another category.")
        return

    summarizer = NewsSummarizer()
    results = summarizer.process_articles(articles)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['article']['title']}")
        print(f"   Source: {result['article']['source']}")
        print(f"   📝 Summary ({result['providers']['summary']}): {result['summary']}")
        print(f"   🎭 Sentiment ({result['providers']['sentiment']}): {result['sentiment']}")
        if result["fallback_used"]:
            print("   ⚠️  Fallback provider was used")

    summarizer.budget_manager.print_summary()
    path = save_results(results, summarizer.budget_manager.get_summary())
    print(f"\n💾 Results saved to {path}")


if __name__ == "__main__":
    main()
