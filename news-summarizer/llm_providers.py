"""Small OpenAI and Cohere wrappers with token and cost tracking."""

import os
import sys
from dataclasses import dataclass
from typing import Any

import cohere
from openai import OpenAI

from config import COHERE_API_KEY, OPENAI_API_KEY


@dataclass(frozen=True)
class ProviderPricing:
    """Estimated USD prices per million tokens for a provider model."""

    input_per_million: float
    output_per_million: float


@dataclass
class UsageRecord:
    """Token usage and estimated cost for one provider request."""

    provider: str
    input_tokens: int
    output_tokens: int
    cost: float


class CostTracker:
    """Collect usage records and report estimated costs."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def record(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        pricing: ProviderPricing,
    ) -> UsageRecord:
        """Save one request's token counts and estimated USD cost."""
        cost = (
            input_tokens * pricing.input_per_million
            + output_tokens * pricing.output_per_million
        ) / 1_000_000
        record = UsageRecord(provider, input_tokens, output_tokens, cost)
        self.records.append(record)
        return record

    @property
    def total_cost(self) -> float:
        """Return the estimated cost across recorded requests."""
        return sum(record.cost for record in self.records)

    def summary(self) -> str:
        """Format usage totals grouped by provider."""
        if not self.records:
            return "No provider usage recorded."

        lines = ["Usage and estimated cost:"]
        providers = sorted({record.provider for record in self.records})
        for provider in providers:
            records = [r for r in self.records if r.provider == provider]
            input_tokens = sum(r.input_tokens for r in records)
            output_tokens = sum(r.output_tokens for r in records)
            cost = sum(r.cost for r in records)
            lines.append(
                f"  {provider}: {input_tokens} input tokens, "
                f"{output_tokens} output tokens, estimated ${cost:.6f}"
            )
        lines.append(f"  Total estimated cost: ${self.total_cost:.6f}")
        return "\n".join(lines)


class OpenAIProvider:
    """Generate text using OpenAI's chat completions API."""

    MODEL = "gpt-4o-mini"
    PRICING = ProviderPricing(input_per_million=0.15, output_per_million=0.60)

    def __init__(
        self, api_key: str | None = None, cost_tracker: CostTracker | None = None
    ) -> None:
        key = (api_key or OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")).strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is missing.")
        self.client = OpenAI(api_key=key)
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate a response and record actual token usage."""
        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        if not response.choices or response.choices[0].message.content is None:
            raise RuntimeError("OpenAI returned no generated text.")
        if response.usage is None:
            raise RuntimeError("OpenAI response did not include token usage.")
        self.cost_tracker.record(
            "OpenAI",
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            self.PRICING,
        )
        return response.choices[0].message.content


class CohereProvider:
    """Generate text using Cohere's chat API."""

    MODEL = "command-r-08-2024"
    PRICING = ProviderPricing(input_per_million=0.15, output_per_million=0.60)

    def __init__(
        self, api_key: str | None = None, cost_tracker: CostTracker | None = None
    ) -> None:
        key = (api_key or COHERE_API_KEY or os.getenv("COHERE_API_KEY", "")).strip()
        if not key:
            raise ValueError("COHERE_API_KEY is missing.")
        self.client = cohere.Client(key)
        self.cost_tracker = cost_tracker if cost_tracker is not None else CostTracker()

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate a response and record token usage reported by Cohere."""
        response = self.client.chat(
            model=self.MODEL,
            message=prompt,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        text = response.text
        if not text:
            raise RuntimeError("Cohere returned no generated text.")

        meta: Any = response.meta
        billed_units = getattr(meta, "billed_units", None)
        input_tokens = getattr(billed_units, "input_tokens", None)
        output_tokens = getattr(billed_units, "output_tokens", None)
        if input_tokens is None or output_tokens is None:
            raise RuntimeError("Cohere response did not include billed token usage.")
        self.cost_tracker.record(
            "Cohere", input_tokens, output_tokens, self.PRICING
        )
        return text


def main() -> int:
    """Send a small test prompt to each configured provider."""
    tracker = CostTracker()
    providers = [
        ("OpenAI", OPENAI_API_KEY, OpenAIProvider),
        ("Cohere", COHERE_API_KEY, CohereProvider),
    ]
    missing = [name for name, key, _ in providers if not key]
    if missing:
        print("Missing API key(s): " + ", ".join(missing), file=sys.stderr)
        print("Set the matching key in .env before running this test.", file=sys.stderr)
        return 1

    for name, _, provider_type in providers:
        provider = provider_type(cost_tracker=tracker)
        print(f"\n{name} test:")
        print(provider.generate("Reply with one short greeting.", max_tokens=40))

    print("\n" + tracker.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())