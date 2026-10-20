import time
from cohere.core.api_error import ApiError
from cohere.core.api_error import ApiError
from openai import OpenAI
import cohere
from cohere.types import UserChatMessageV2
import time
import random
from typing import Callable, TypeVar
from openai import RateLimitError, APITimeoutError, APIConnectionError

from config import get_config

T = TypeVar("T")

class LLMProviders:
    """Manage OpenAI and Cohere API integrations."""
    
    def __init__(self):
        self.config = get_config()

        self.openai = OpenAI(
            api_key=self.config.openai_api_key,
            timeout=self.config.request_timeout,
        )

        self.cohere = cohere.ClientV2(
            api_key=self.config.cohere_api_key,
            timeout=self.config.request_timeout,
        )

        self.total_cost = 0.0
        self.last_request_time = 0.0

    def summarize_with_openai(self, text):
        """Summarize text using OpenAI."""
        self.check_budget()
        response = self.retry_request(
            lambda: self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the text in 2-3 sentences.",
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
            )
        )

        summary = response.choices[0].message.content

        if summary is None:
            raise ValueError("OpenAI returned no summary.")

        usage = response.usage

        if usage is None:
            raise ValueError("OpenAI did not return token usage.")

        # Example USD rates per million tokens.
        # Verify current pricing before production use.
        input_cost = (
            usage.prompt_tokens * 0.15 / 1_000_000
        )
        output_cost = (
            usage.completion_tokens * 0.60 / 1_000_000
        )

        cost = input_cost + output_cost
        self.total_cost += cost

        return {
            "summary": summary,
            "cost": cost,
        }

    def sentiment_with_cohere(self, text):
        """Analyze sentiment using Cohere."""
        self.check_budget()
        response = self.retry_cohere_request(
            lambda: self.cohere.chat(
                model="command-a-03-2025",
                messages=[
                    UserChatMessageV2(
                        content=(
                            "Classify the sentiment of this text as "
                            "positive, negative, or neutral. "
                            "Give one short explanation.\n\n"
                            f"{text}"
                        )
                    )
                ],
            )
        )

        content = response.message.content or []

        sentiment = "".join(
            part.text
            for part in content
            if part.type == "text"
        )

        if not sentiment:
            raise ValueError("Cohere returned no sentiment.")

        usage = response.usage
        billed_units = usage.billed_units if usage else None

        input_tokens = (
            billed_units.input_tokens
            if billed_units
            and billed_units.input_tokens is not None
            else 0
        )

        output_tokens = (
            billed_units.output_tokens
            if billed_units
            and billed_units.output_tokens is not None
            else 0
        )

        cost = (
            input_tokens * 2.50
            + output_tokens * 10.00
        ) / 1_000_000

        self.total_cost += cost

        return {
            "sentiment": sentiment,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        }

    def retry_request(self, operation: Callable[[], T]) -> T:
        """Retry temporary OpenAI API failures."""
        for attempt in range(self.config.max_retries + 1):
            try:
                self.apply_rate_limit()
                return operation()

            except (RateLimitError, APITimeoutError, APIConnectionError):
                if attempt == self.config.max_retries:
                    raise

                delay = min(2 ** attempt, 30) + random.uniform(0, 1)
                print(f"Temporary API failure. Retrying in {delay:.1f}s...")
                time.sleep(delay)

        raise RuntimeError("Retry attempts exhausted.")

    
    def summarize(self, text):
        """Summarize with OpenAI, falling back to Cohere."""
        try:
            return self.summarize_with_openai(text)
        except (RateLimitError, APITimeoutError, APIConnectionError) as error:
            print(f"OpenAI unavailable: {error}")
            print("Falling back to Cohere...")
            return self.summarize_with_cohere(text)

    def summarize_with_cohere(self, text):
        """Summarize text using Cohere."""
        self.check_budget()
        response = self.retry_cohere_request(
            lambda: self.cohere.chat(
                model="command-a-03-2025",
                messages=[
                    UserChatMessageV2(
                        content=f"Summarize this text in 2-3 sentences:\n\n{text}"
                    )
                ],
            )
        )

        content = response.message.content or []
        summary = "".join(
            part.text for part in content if part.type == "text"
        )

        if not summary:
            raise ValueError("Cohere returned no summary.")
        usage = response.usage
        billed_units = usage.billed_units if usage else None

        input_tokens = (
            billed_units.input_tokens
            if billed_units and billed_units.input_tokens is not None
            else 0
        )

        output_tokens = (
            billed_units.output_tokens
            if billed_units and billed_units.output_tokens is not None
            else 0
        )

        cost = (
            input_tokens * 2.50
            + output_tokens * 10.00
        ) / 1_000_000

        self.total_cost += cost
        return {"summary": summary, "cost": cost}
    
    def sentiment_with_openai(self, text):
        """Analyze sentiment using OpenAI as fallback."""
        self.check_budget()
        response = self.retry_request(
            lambda: self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Classify sentiment as positive, negative, "
                            "or neutral. Give one short explanation."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            )
        )

        sentiment = response.choices[0].message.content
        if not sentiment:
            raise ValueError("OpenAI returned no sentiment.")

        usage = response.usage
        if usage is None:
            raise ValueError("OpenAI returned no token usage.")

        cost = (
            usage.prompt_tokens * 0.15
            + usage.completion_tokens * 0.60
        ) / 1_000_000

        self.total_cost += cost

        return {"sentiment": sentiment, "cost": cost}
    def analyze_sentiment(self, text):
        """Use Cohere first, then OpenAI for temporary failures."""
        try:
            return self.sentiment_with_cohere(text)

        except ApiError as error:
            if error.status_code not in (429, 500, 502, 503, 504):
                raise

            print("Cohere temporarily unavailable. Falling back to OpenAI...")
            return self.sentiment_with_openai(text)

    def check_budget(self):
        """Check whether tracked spending has reached the budget."""
        if self.total_cost >= self.config.daily_budget:
            raise RuntimeError(
                f"API budget reached: ${self.total_cost:.6f} "
                f"of ${self.config.daily_budget:.2f}"
            )

    def apply_rate_limit(self):
        """Space API requests at least one second apart."""
        now = time.monotonic()
        elapsed = now - self.last_request_time

        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        self.last_request_time = time.monotonic()


    def retry_cohere_request(self, operation):
        """Retry temporary Cohere failures with exponential backoff."""
        for attempt in range(self.config.max_retries + 1):
            try:
                self.apply_rate_limit()
                return operation()

            except ApiError as error:
                if error.status_code not in (429, 500, 502, 503, 504):
                    raise

                if attempt == self.config.max_retries:
                    raise

                delay = min(2 ** attempt, 30) + random.uniform(0, 1)
                print(f"Cohere retry in {delay:.1f}s...")
                time.sleep(delay)

        raise RuntimeError("Cohere retry attempts exhausted.")


        

if __name__ == "__main__":
    providers = LLMProviders()

    sample_text = (
        "A technology company launched a new AI tool "
        "that helps businesses automate repetitive tasks."
    )

    print("Testing OpenAI...")

    summary = providers.summarize(sample_text)

    print("Summary:", summary["summary"])
    print(f"Summary cost: ${summary['cost']:.6f}" if summary["cost"] is not None else "Summary cost: not yet calculated")

    print("\nTesting Cohere...")

    sentiment = providers.sentiment_with_cohere(
        summary["summary"]
    )

    print("Sentiment:", sentiment["sentiment"])
    print(
        "Cohere tokens:",
        sentiment["input_tokens"],
        "input,",
        sentiment["output_tokens"],
        "output",
    )

    print(f"Cohere cost: ${sentiment['cost']:.6f}")
    print(f"\nTotal API cost: ${providers.total_cost:.6f}")

 
    
    from openai import APIConnectionError
    from unittest.mock import Mock, patch

    
    

   
    