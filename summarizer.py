
import cohere
from openai import OpenAI

from config import OPENAI_API_KEY, COHERE_API_KEY
from news_api import fetch_news
from llm_providers import calculate_cost
from retry_utils import retry
from budget_tracker import check_budget, record_cost
from budget_tracker import BudgetExceededError

# ==========================================
# INITIALIZE API CLIENTS
# ==========================================

openai_client = OpenAI(api_key=OPENAI_API_KEY)
cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_article_text(article):
    """Prepare article content for summarization."""

    title = article.get("title") or ""
    description = article.get("description") or ""
    content = article.get("content") or ""

    return (
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Content: {content}"
    )


def get_cohere_text(response):
    """Extract text from a Cohere response."""

    return " ".join(
        block.text
        for block in response.message.content
        if block.type == "text"
    ).strip()


def track_cohere_cost(response):
    """Calculate and record Cohere API costs."""

    usage = getattr(response, "usage", None)
    tokens = getattr(usage, "tokens", None)

    if tokens is None:
        print("Cohere token usage unavailable.")
        return

    input_tokens = tokens.input_tokens or 0
    output_tokens = tokens.output_tokens or 0

    cost = calculate_cost(
        input_tokens,
        output_tokens,
        input_rate=2.50,
        output_rate=10.00
    )

    print(
        f"Cohere tokens: "
        f"{input_tokens} input, "
        f"{output_tokens} output"
    )

    print(f"Cohere estimated cost: ${cost:.6f}")

    record_cost(cost)


# ==========================================
# OPENAI SUMMARIZATION
# ==========================================

@retry(max_retries=2)
def summarize_article(article):
    """Summarize an article using OpenAI."""

    check_budget()

    article_text = get_article_text(article)

    prompt = f"""
Summarize the following technology news article
in 2-3 clear sentences.

Use only the information provided.
Do not invent details.

ARTICLE:
{article_text}
"""

    response = openai_client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        max_output_tokens=150
    )

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    cost = calculate_cost(
        input_tokens,
        output_tokens,
        input_rate=0.15,
        output_rate=0.60
    )

    print(
        f"OpenAI tokens: "
        f"{input_tokens} input, "
        f"{output_tokens} output"
    )

    print(f"OpenAI estimated cost: ${cost:.6f}")

    record_cost(cost)

    return response.output_text


# ==========================================
# COHERE SENTIMENT ANALYSIS
# ==========================================

@retry(max_retries=2)
def analyze_sentiment(summary):
    """Analyze sentiment using Cohere."""

    check_budget()

    response = cohere_client.chat(
        model="command-a-03-2025",
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze the sentiment of this news summary. "
                    "Reply with only one word: "
                    "Positive, Negative, or Neutral.\n\n"
                    f"{summary}"
                )
            }
        ]
    )

    track_cohere_cost(response)

    return get_cohere_text(response)


# ==========================================
# FALLBACK: OPENAI -> COHERE
# ==========================================

def summarize_with_fallback(article):
    """
    Try OpenAI first.
    If OpenAI fails, use Cohere.
    """

    try:
        print("Trying OpenAI...")

        summary = summarize_article(article)

        print("Provider used: OpenAI")

        return summary
    except BudgetExceededError:
        raise
    except Exception as error:
        print(
            f"OpenAI failed: "
            f"{type(error).__name__}: {error}"
        )

        # Do not bypass the daily budget limit.
        check_budget()

        print("Switching to Cohere...")

        article_text = get_article_text(article)

        response = cohere_client.chat(
            model="command-a-03-2025",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Summarize this technology news article "
                        "in 2-3 clear sentences. "
                        "Use only the supplied information.\n\n"
                        f"{article_text}"
                    )
                }
            ]
        )

        track_cohere_cost(response)

        print("Provider used: Cohere (fallback)")

        return get_cohere_text(response)


# ==========================================
# MAIN APPLICATION
# ==========================================

if __name__ == "__main__":

    print("\n=== News Summarizer ===\n")

    articles = fetch_news(limit=1)

    for article in articles:

        print("TITLE:", article.get("title"))

        summary = summarize_with_fallback(article)

        print("\nSUMMARY:", summary)

        sentiment = analyze_sentiment(summary)

        print("\nSENTIMENT:", sentiment)

        print("\nSOURCE:", article.get("url"))
