"""The workflow: News API -> OpenAI summary -> Cohere sentiment -> output record."""
import re
from news_api import fetch_top_headlines
from llm_providers import LLMProviders

ALLOWED_SENTIMENTS = ["positive", "negative", "neutral"]

def unsupported_numbers(summary, source_text):
    """Return numbers in the summary that do not appear in the source text."""
    numbers = re.findall(r"\d+(?:\.\d+)?", summary)
    return [n for n in numbers if n not in source_text]


def article_text(article):
    """Pick the richest text available. Mark it if we only have the title."""
    text = article["content"] or article["description"]
    if text:
        return text, False
    return article["title"], True          # thin input: title only


def build_summary_prompt(article):
    text, title_only = article_text(article)
    warning = ("Only the headline is available. Summarize ONLY what the headline says. "
               "Do not invent details.\n"
               "Use ONLY facts stated in the text below. Do not add numbers, names or findings from your own knowledge.\n") if title_only else ""
    return (f"{warning}Summarize this news article in 2 sentences for a general reader.\n\n"
            f"Title: {article['title']}\nText: {text}")


def build_sentiment_prompt(summary):
    return ("Classify the overall sentiment of this news summary.\n"
            f"Allowed labels: {', '.join(ALLOWED_SENTIMENTS)}\n"
            "Answer with exactly ONE lowercase label and nothing else.\n\n"
            f"Summary: {summary}\n\nLabel:")


def clean_sentiment(raw):
    """Turn the model's answer into one allowed label, or 'unknown'."""
    word = raw.strip().lower().strip(".!\"' ")
    return word if word in ALLOWED_SENTIMENTS else "unknown"


class NewsSummarizer:
    """Runs the full pipeline for a list of articles."""

    def __init__(self, llm=None):
        self.llm = llm or LLMProviders()

    def process_article(self, article):
        source_text, title_only = article_text(article)
        summary, summary_provider = self.llm.ask_with_fallback(
            build_summary_prompt(article), primary="openai")
        raw_sentiment, sentiment_provider = self.llm.ask_with_fallback(
            build_sentiment_prompt(summary), primary="cohere")
        return {
            "title": article["title"],
            "source": article["source"],
            "url": article["url"],
            "summary": summary,
            "sentiment": clean_sentiment(raw_sentiment),
            "summary_provider": summary_provider,
            "sentiment_provider": sentiment_provider,
            "title_only": title_only,
            "unsupported_numbers": unsupported_numbers(
                summary, source_text + " " + article["title"]),
        }

    def process_articles(self, articles):
        results = []
        for i, article in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] {article['title'][:70]}")
            try:
                record = self.process_article(article)
                print(f"   ✅ summary by {record['summary_provider']}, "
                      f"sentiment by {record['sentiment_provider']}: {record['sentiment']}")
                results.append(record)
            except Exception as e:
                print(f"   ❌ skipped: {e}")      # one bad article doesn't stop the run
        return results


if __name__ == "__main__":
    articles = fetch_top_headlines(page_size=2)
    summarizer = NewsSummarizer()
    results = summarizer.process_articles(articles)

    print("\n" + "=" * 60)
    for r in results:
        print(f"\n📰 {r['title']}")
        print(f"   {r['summary']}")
        print(f"   Sentiment: {r['sentiment']}"
              + ("   ⚠️ title only" if r["title_only"] else ""))
    if r["unsupported_numbers"]:
            print(f"   🔎 Check: numbers not in source: {', '.join(r['unsupported_numbers'])}")
    print("\n💰 " + summarizer.llm.costs.summary())