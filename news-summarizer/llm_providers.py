
from openai import OpenAI

try:
    from anthropic import Anthropic
except ImportError:  # Keep unit tests runnable before dependencies are installed.
    Anthropic = None

from config import Config


class LLMProviders:
    def __init__(self):
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
        if Anthropic is None:
            raise ImportError("Install dependencies with: pip install -r requirements.txt")
        self.anthropic_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.total_cost = 0.0

    def summarize(self, text):
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this news in 2 sentences:\n{text}",
                }
            ],
        )

        if response.usage:
            self.total_cost += (
                response.usage.prompt_tokens * 0.00000015
                + response.usage.completion_tokens * 0.00000060
            )

        return response.choices[0].message.content

    def analyze_sentiment(self, text):
        response = self.anthropic_client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": (
                    "Classify the sentiment as positive, negative, or neutral. "
                    f"Return only the classification.\n\n{text}"
                ),
            }],
        )
        if response.usage:
            self.total_cost += (
                response.usage.input_tokens * 0.0000008
                + response.usage.output_tokens * 0.000004
            )
        return response.content[0].text.strip()
