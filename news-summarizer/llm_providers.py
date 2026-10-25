import os

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = (
    anthropic.Anthropic(api_key=anthropic_api_key)
    if anthropic_api_key
    else None
)


def summarize_with_openai(article_text):
    """Summarize an article with OpenAI."""
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Summarize the news article in 2-3 clear sentences.",
            },
            {"role": "user", "content": article_text},
        ],
    )

    summary = response.choices[0].message.content
    usage = response.usage
    return {
        "text": summary,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
    }


def analyze_sentiment_with_anthropic(article_text):
    """Analyze an article's sentiment with Anthropic Claude."""
    if anthropic_client is None:
        raise ValueError("ANTHROPIC_API_KEY is missing from the .env file")

    response = anthropic_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        system=(
            "Classify the news article as positive, negative, or neutral. "
            "Give one short reason."
        ),
        messages=[{"role": "user", "content": article_text}],
    )
    return response.content[0].text


def analyze_sentiment_with_fallback(article_text):
    """Try Anthropic first; use OpenAI if Anthropic fails."""
    try:
        return {
            "provider": "Anthropic",
            "sentiment": analyze_sentiment_with_anthropic(article_text),
        }
    except Exception as error:
        print(f"Anthropic failed; using OpenAI instead. Reason: {error}")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the sentiment as positive, negative, or "
                        "neutral. Give one short reason."
                    ),
                },
                {"role": "user", "content": article_text},
            ],
        )
        return {
            "provider": "OpenAI fallback",
            "sentiment": response.choices[0].message.content,
        }


if __name__ == "__main__":
    test_text = (
        "A technology company announced a new product that received "
        "positive reviews from customers."
    )

    summary_result = summarize_with_openai(test_text)
    print("Summary:", summary_result["text"])
    print(
        "OpenAI tokens:",
        summary_result["input_tokens"],
        "input,",
        summary_result["output_tokens"],
        "output",
    )

    sentiment_result = analyze_sentiment_with_fallback(test_text)
    print("Sentiment provider:", sentiment_result["provider"])
    print("Sentiment:", sentiment_result["sentiment"])
