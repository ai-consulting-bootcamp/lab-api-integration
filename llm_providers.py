"""Provider adapters, retry handling, fallback, and simple cost tracking."""

from dataclasses import dataclass
import time
from typing import Callable

from config import Config, get_config


class ProviderError(RuntimeError):
    """Raised when an LLM provider cannot produce a response."""


@dataclass
class ProviderResponse:
    text: str
    provider: str
    cost: float


class CostTracker:
    """Accumulate provider costs and enforce the configured daily budget."""

    def __init__(self, budget: float = 5.0):
        self.budget = budget
        self.total = 0.0

    def add(self, amount: float) -> None:
        if self.total + amount > self.budget:
            raise ProviderError("Daily budget exceeded")
        self.total += amount

    def summary(self) -> dict[str, float]:
        return {"total": round(self.total, 6), "budget": self.budget, "remaining": round(self.budget - self.total, 6)}


class OpenAIProvider:
    name = "openai"

    def __init__(self, config: Config | None = None, client=None):
        self.config = config or get_config()
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=self.config.openai_api_key)
        self.client = client

    def complete(self, prompt: str) -> ProviderResponse:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", 0) or 0
        return ProviderResponse(text, self.name, tokens * 0.00000015)


class CohereProvider:
    name = "cohere"

    def __init__(self, config: Config | None = None, client=None):
        self.config = config or get_config()
        if client is None:
            import cohere
            client = cohere.ClientV2(api_key=self.config.cohere_api_key)
        self.client = client

    def complete(self, prompt: str) -> ProviderResponse:
        response = self.client.chat(model="command-r7b-12-2024", messages=[{"role": "user", "content": prompt}])
        text = response.message.content[0].text.strip()
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "tokens", None)
        tokens = getattr(tokens, "input_tokens", 0) + getattr(tokens, "output_tokens", 0) if tokens else 0
        return ProviderResponse(text, self.name, tokens * 0.0000005)


def ask_with_fallback(
    prompt: str,
    primary,
    fallback,
    tracker: CostTracker | None = None,
    retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> ProviderResponse:
    """Try the primary provider, then the fallback, retrying transient failures."""
    errors = []
    for provider in (primary, fallback):
        for attempt in range(max(1, retries)):
            try:
                result = provider.complete(prompt)
                if tracker:
                    tracker.add(result.cost)
                return result
            except Exception as exc:  # providers expose different exception types
                errors.append(f"{provider.name}: {exc}")
                if attempt < retries - 1:
                    sleep(0.1 * (attempt + 1))
    raise ProviderError("All providers failed: " + "; ".join(errors))


if __name__ == "__main__":
    config = get_config()
    tracker = CostTracker(config.daily_budget)
    result = ask_with_fallback("Reply with the word ready.", OpenAIProvider(config), CohereProvider(config), tracker, config.max_retries)
    print(result.provider, result.text)
    print(tracker.summary())
