"""LLM providers: OpenAI and Cohere with cost tracking, rate limiting,
retries, and fallback."""
import time

import cohere
from openai import OpenAI

from config import Config

# USD per 1 million tokens. Prices change: check the providers' pricing pages.
PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "command-a-03-2025": {"input": 2.50, "output": 10.00},
}
# Deliberately high, so unknown models are never under-counted
DEFAULT_PRICE = {"input": 5.00, "output": 15.00}


class BudgetExceededError(Exception):
    """Raised when spending has reached the daily budget."""


class CostTracker:
    """Records the cost of every LLM call and enforces the daily budget."""

    def __init__(self, daily_budget=None):
        self.daily_budget = (
            daily_budget if daily_budget is not None else Config.DAILY_BUDGET
        )
        self.total_cost = 0.0
        self.requests = []

    @staticmethod
    def calculate_cost(model, input_tokens, output_tokens):
        """Return the USD cost of one call."""
        price = PRICING.get(model, DEFAULT_PRICE)
        return (
            input_tokens * price["input"] + output_tokens * price["output"]
        ) / 1_000_000

    def check_budget(self):
        """Raise BudgetExceededError if the budget is used up."""
        if self.total_cost >= self.daily_budget:
            raise BudgetExceededError(
                f"Daily budget of ${self.daily_budget:.2f} reached "
                f"(spent ${self.total_cost:.4f})"
            )

    def record(self, provider, model, input_tokens, output_tokens):
        """Log one call and add its cost to the running total."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        self.total_cost += cost
        self.requests.append({
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
        })
        return cost

    def summary(self):
        """Return totals for reporting."""
        return {
            "total_requests": len(self.requests),
            "total_cost": self.total_cost,
            "budget_remaining": self.daily_budget - self.total_cost,
        }


class RateLimiter:
    """Allows at most max_calls per period (seconds); waits when full."""

    def __init__(self, max_calls, period=60.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    def wait_if_needed(self):
        """Sleep just long enough to stay under the limit."""
        now = time.monotonic()
        self.calls = [t for t in self.calls if now - t < self.period]
        if len(self.calls) >= self.max_calls:
            sleep_for = self.period - (now - self.calls[0])
            print(f"  ⏳ Rate limit reached, waiting {sleep_for:.1f}s")
            time.sleep(sleep_for)
        self.calls.append(time.monotonic())


class LLMProvider:
    """Shared logic for all providers: budget check, rate limit, retries."""

    name = "base"

    def __init__(self, model, cost_tracker, rate_limiter):
        self.model = model
        self.cost_tracker = cost_tracker
        self.rate_limiter = rate_limiter

    def complete(self, prompt, max_tokens=300):
        """Send a prompt and return the response text."""
        self.cost_tracker.check_budget()
        last_error = None
        for attempt in range(1, Config.MAX_RETRIES + 1):
            self.rate_limiter.wait_if_needed()
            try:
                text, input_tokens, output_tokens = self._call(prompt, max_tokens)
                self.cost_tracker.record(
                    self.name, self.model, input_tokens, output_tokens
                )
                return text
            except Exception as error:  # noqa: BLE001 - any API error is retryable here
                last_error = error
                if attempt < Config.MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  ⚠ {self.name} attempt {attempt} failed, retrying in {wait}s")
                    time.sleep(wait)
        raise RuntimeError(
            f"{self.name} failed after {Config.MAX_RETRIES} attempts: {last_error}"
        )

    def _call(self, prompt, max_tokens):
        """Provider-specific API call. Returns (text, input_tokens, output_tokens)."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI chat completions."""

    name = "openai"

    def __init__(self, cost_tracker, rate_limiter=None, model=None):
        super().__init__(
            model or Config.OPENAI_MODEL,
            cost_tracker,
            rate_limiter or RateLimiter(max_calls=20),
        )
        # max_retries=0 because our own retry loop handles retries
        self.client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            timeout=Config.REQUEST_TIMEOUT,
            max_retries=0,
        )

    def _call(self, prompt, max_tokens):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        usage = response.usage
        text = response.choices[0].message.content.strip()
        return text, usage.prompt_tokens, usage.completion_tokens


class CohereProvider(LLMProvider):
    """Cohere chat (v2 API)."""

    name = "cohere"

    def __init__(self, cost_tracker, rate_limiter=None, model=None):
        super().__init__(
            model or Config.COHERE_MODEL,
            cost_tracker,
            rate_limiter or RateLimiter(max_calls=20),
        )
        self.client = cohere.ClientV2(
            api_key=Config.COHERE_API_KEY,
            timeout=Config.REQUEST_TIMEOUT,
        )

    def _call(self, prompt, max_tokens):
        response = self.client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        text = response.message.content[0].text.strip()
        billed = response.usage.billed_units
        return text, int(billed.input_tokens or 0), int(billed.output_tokens or 0)


class ProviderWithFallback:
    """Tries the primary provider; if it fails, uses the backup."""

    def __init__(self, primary, backup):
        self.primary = primary
        self.backup = backup

    def complete(self, prompt, max_tokens=300):
        """Return (text, name_of_provider_that_answered)."""
        try:
            return self.primary.complete(prompt, max_tokens), self.primary.name
        except BudgetExceededError:
            raise  # never fall back to spend more money
        except Exception as error:  # noqa: BLE001
            print(f"  ⚠ {self.primary.name} failed ({error}), falling back to {self.backup.name}")
            return self.backup.complete(prompt, max_tokens), self.backup.name


if __name__ == "__main__":
    tracker = CostTracker()
    openai_provider = OpenAIProvider(tracker)
    cohere_provider = CohereProvider(tracker)

    for provider in (openai_provider, cohere_provider):
        print(f"Testing {provider.name} ({provider.model})...")
        try:
            reply = provider.complete("Say hello in exactly five words.", max_tokens=20)
            print(f"  ✓ {reply}")
        except Exception as error:  # noqa: BLE001
            print(f"  ✗ {error}")

    stats = tracker.summary()
    print()
    print("Cost tracking:")
    print(f"  Requests:         {stats['total_requests']}")
    print(f"  Total cost:       ${stats['total_cost']:.6f}")
    print(f"  Budget remaining: ${stats['budget_remaining']:.4f}")