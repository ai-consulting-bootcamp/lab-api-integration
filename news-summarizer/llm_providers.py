"""Talk to OpenAI and Cohere with retries, fallback, rate limiting and cost tracking."""
import time
import cohere
from openai import OpenAI
from config import get_config

# Prices in USD per 1 million tokens (check the providers' pricing pages)
PRICES = {
    "openai": {"model": "gpt-4o-mini", "input": 0.15, "output": 0.60},
    "cohere": {"model": "command-r7b-12-2024", "input": 0.0375, "output": 0.15},
}
MIN_SECONDS_BETWEEN_CALLS = 1.0   # simple rate limiting


class BudgetExceededError(Exception):
    """Raised when the daily budget would be exceeded."""


class CostTracker:
    """Adds up tokens and cost per provider and enforces the daily budget."""

    def __init__(self, daily_budget):
        self.daily_budget = daily_budget
        self.total_cost = 0.0
        self.calls = []

    def add(self, provider, input_tokens, output_tokens):
        price = PRICES[provider]
        cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
        self.total_cost += cost
        self.calls.append({"provider": provider, "input": input_tokens,
                           "output": output_tokens, "cost": cost})
        return cost

    def check_budget(self):
        if self.total_cost >= self.daily_budget:
            raise BudgetExceededError(
                f"[cost] Daily budget ${self.daily_budget:.2f} reached "
                f"(spent ${self.total_cost:.4f}). Increase DAILY_BUDGET in .env.")

    def summary(self):
        lines = [f"Total calls: {len(self.calls)} | Total cost: ${self.total_cost:.6f}"]
        for provider in PRICES:
            calls = [c for c in self.calls if c["provider"] == provider]
            if calls:
                tokens_in = sum(c["input"] for c in calls)
                tokens_out = sum(c["output"] for c in calls)
                cost = sum(c["cost"] for c in calls)
                lines.append(f"  {provider}: {len(calls)} calls | "
                             f"input {tokens_in} tokens | output {tokens_out} tokens | "
                             f"${cost:.6f}")
        return "\n".join(lines)


class LLMProviders:

    """One door to both AI providers."""

    def __init__(self):
        self.config = get_config()
        self.openai_client = OpenAI(api_key=self.config.openai_api_key,
                                    timeout=self.config.request_timeout)
        self.cohere_client = cohere.ClientV2(api_key=self.config.cohere_api_key)
        self.costs = CostTracker(self.config.daily_budget)
        self._last_call = 0.0

    def _wait_for_rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < MIN_SECONDS_BETWEEN_CALLS:
            time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)
        self._last_call = time.time()

    def call_openai(self, prompt):
        response = self.openai_client.chat.completions.create(
            model=PRICES["openai"]["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        usage = response.usage
        self.costs.add("openai", usage.prompt_tokens, usage.completion_tokens)
        return response.choices[0].message.content.strip()

    def call_cohere(self, prompt):
        response = self.cohere_client.chat(
            model=PRICES["cohere"]["model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        units = response.usage.billed_units
        self.costs.add("cohere", int(units.input_tokens or 0), int(units.output_tokens or 0))
        return response.message.content[0].text.strip()

    def _call_with_retry(self, provider, prompt):
        call = self.call_openai if provider == "openai" else self.call_cohere
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            self.costs.check_budget()
            self._wait_for_rate_limit()
            try:
                return call(prompt)
            except Exception as e:
                last_error = e
                if "AuthenticationError" in type(e).__name__:
                    break                              # wrong key: retrying won't help
                wait = 2 ** (attempt - 1)          # 1s, 2s, 4s ... (exponential backoff)
                print(f"   ⚠️  [{provider}] attempt {attempt} failed: "
                      f"{type(e).__name__}. Retrying in {wait}s...")
                time.sleep(wait)
        raise RuntimeError(f"[{provider}] failed: {type(last_error).__name__}")

    def ask_with_fallback(self, prompt, primary="openai"):
        """Try the primary provider; if it fails completely, use the other one."""
        backup = "cohere" if primary == "openai" else "openai"
        try:
            return self._call_with_retry(primary, prompt), primary
        except BudgetExceededError:
            raise                                   # never fall back past the budget
        except Exception as e:
            print(f"   🔁 FALLBACK: {primary} unavailable ({e}). Switching to {backup}.")
            return self._call_with_retry(backup, prompt), backup


if __name__ == "__main__":
    llm = LLMProviders()
    print("Testing OpenAI...")
    answer, used = llm.ask_with_fallback("Say hello in 5 words.", primary="openai")
    print(f"✅ [{used}] {answer}\n")

    print("Testing Cohere...")
    answer, used = llm.ask_with_fallback("Say hello in 5 words.", primary="cohere")
    print(f"✅ [{used}] {answer}\n")

    print("💰 Cost summary")
    print(llm.costs.summary())