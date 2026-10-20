
import cohere
from openai import OpenAI

from config import OPENAI_API_KEY, COHERE_API_KEY


# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)


def test_openai():
    """Test OpenAI and display token usage."""

    response = openai_client.responses.create(
        model="gpt-4o-mini",
        input="Explain artificial intelligence in one sentence.",
        max_output_tokens=100
    )

    print("OpenAI response:")
    print(response.output_text)

    print("\nToken usage:")
    print("Input:", response.usage.input_tokens)
    print("Output:", response.usage.output_tokens)


def test_cohere():
    """Test Cohere sentiment analysis and token usage."""

    cohere_client = cohere.ClientV2(api_key=COHERE_API_KEY)

    response = cohere_client.chat(
        model="command-a-03-2025",
        messages=[
            {
                "role": "user",
                "content": (
                    "Analyze the sentiment of this news headline. "
                    "Reply with only Positive, Negative, or Neutral: "
                    "'New technology helps doctors detect cancer earlier.'"
                )
            }
        ]
    )

    print("\nCohere response:")

    for block in response.message.content:
        if block.type == "text":
            print(block.text)

    print("\nToken usage:")
    print("Input:", response.usage.tokens.input_tokens)
    print("Output:", response.usage.tokens.output_tokens)


if __name__ == "__main__":
    test_openai()
    test_cohere()

def calculate_cost(input_tokens, output_tokens,
                   input_rate, output_rate):
    """Estimate API cost in USD using per-million-token rates."""

    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate

    return input_cost + output_cost

def calculate_cost(input_tokens, output_tokens, input_rate, output_rate):
    """Calculate estimated API cost in USD."""
    input_cost = (input_tokens / 1_000_000) * input_rate
    output_cost = (output_tokens / 1_000_000) * output_rate
    return input_cost + output_cost
