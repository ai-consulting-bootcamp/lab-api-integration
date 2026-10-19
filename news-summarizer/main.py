"""Interactive app: choose a category, process articles, see results and costs."""
import json
from datetime import datetime
from news_api import fetch_top_headlines
from summarizer import NewsSummarizer
from llm_providers import BudgetExceededError

CATEGORIES = ["technology", "business", "science", "health", "sports", "entertainment", "general"]


def ask(question, default):
    """Ask the user; Enter (or no input at all) uses the default."""
    try:
        answer = input(f"{question} [{default}]: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def choose_category():
    print("Categories: " + ", ".join(CATEGORIES))
    category = ask("Category", "technology").lower()
    if category not in CATEGORIES:
        print(f"   '{category}' is not available, using 'technology'.")
        category = "technology"
    return category


def choose_count():
    raw = ask("How many articles (1-5)", "3")
    if raw.isdigit() and 1 <= int(raw) <= 5:
        return int(raw)
    print("   Please use a number from 1 to 5. Using 3.")
    return 3


def save_results(results, category):
    filename = f"output_{category}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return filename


def main():
    print("=" * 60)
    print("📰  Multi-Provider News Summarizer (OpenAI + Cohere)")
    print("=" * 60)

    category = choose_category()
    count = choose_count()

    print(f"\nFetching {count} '{category}' articles...")
    articles = fetch_top_headlines(category=category, page_size=count)
    if len(articles) < count:
        print(f"   ℹ️ Requested {count}, received {len(articles)} usable articles.")
    if not articles:
        print("❌ No articles returned. Try another category.")
        return


    summarizer = NewsSummarizer()
    try:
        results = summarizer.process_articles(articles)
    except BudgetExceededError as e:
        print(f"\n🛑 {e}")
        return

    for r in results:
        flag = "   ⚠️ title only" if r["title_only"] else ""
        print(f"\n📰 {r['title']}  ({r['source']})")
        print(f"   {r['summary']}")
        print(f"   Sentiment: {r['sentiment']}{flag}")
        print(f"   Providers: summary={r['summary_provider']}, "
              f"sentiment={r['sentiment_provider']}")
        if r["unsupported_numbers"]:
            print(f"   🔎 Check: numbers not in source: {', '.join(r['unsupported_numbers'])}")

    print(f"\n✅ Processed {len(results)}/{len(articles)} articles")
    print("💰 " + summarizer.llm.costs.summary())
    print(f"💾 Saved to {save_results(results, category)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"\n❌ {e}")