"""Unified OpenAI and Cohere client with retries, fallback, and usage tracking."""

import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import cohere
import httpx
import openai

from config import get_config

# Low-cost models suit this application's short prompts and responses.
OPENAI_MODEL = "gpt-4o-mini"
COHERE_MODEL = "command-r-08-2024"

# USD per million input/output tokens. Verify prices periodically.
PRICING = {
    OPENAI_MODEL: (0.15, 0.60),
    COHERE_MODEL: (0.15, 0.60),
}

# Retry temporary failures, not invalid requests or authentication errors.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
OTHER_PROVIDER = {"openai": "cohere", "cohere": "openai"}

# Store usage beside this module so different entry points share one log.
USAGE_LOG = Path(__file__).resolve().parent / "usage_log.jsonl"


class LLMError(Exception):
    """An LLM request failed."""


class BudgetExceededError(LLMError):
    """The configured daily spending threshold was reached."""


@dataclass(frozen=True)
class LLMResponse:
    """Provider response and its measured token usage and estimated cost."""

    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    used_fallback: bool = False


class CostTracker:
    """Track daily API costs using a persistent JSON Lines log.

    The budget is a best-effort threshold, not a guaranteed spending cap.
    It excludes usage outside this application and concurrent in-flight calls.
    Configure provider-side limits for stronger protection.
    """

    def __init__(self, daily_budget, log_file=None):
        self.daily_budget = daily_budget
        self.log_file = Path(log_file) if log_file else None
        self.total = 0.0
        self.by_provider = {}
        self.calls = {}
        self._refresh()

    def calculate(self, model, input_tokens, output_tokens):
        """Estimate the request cost in USD from token counts."""
        input_price, output_price = PRICING[model]
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    def check_budget(self):
        """Reject new calls once logged spending reaches the threshold."""
        self._refresh()
        if self.total >= self.daily_budget:
            raise BudgetExceededError(
                f"Daily budget of ${self.daily_budget:.2f} reached "
                f"(spent ${self.total:.4f})"
            )

    def record(self, response):
        """Record a successful request in memory and, optionally, on disk."""
        self._add(response.provider, response.cost)
        if not self.log_file:
            return

        entry = {
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost": response.cost,
            "used_fallback": response.used_fallback,
        }
        try:
            with self.log_file.open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry) + "\n")
        except OSError as error:
            # A logging failure must not discard a successful API response.
            print(f"⚠️  Could not write {self.log_file.name}: {error}")

    def summary(self):
        """Format the tracked daily spending for display."""
        lines = ["Cost summary:"]
        for provider, cost in self.by_provider.items():
            lines.append(f"  {provider:<7} {self.calls[provider]} calls  ${cost:.6f}")
        lines.append(f"  total   ${self.total:.6f} of ${self.daily_budget:.2f} budget")
        return "\n".join(lines)

    def _add(self, provider, cost):
        """Update the in-memory totals for one request."""
        self.total += cost
        self.by_provider[provider] = self.by_provider.get(provider, 0.0) + cost
        self.calls[provider] = self.calls.get(provider, 0) + 1

    def _refresh(self):
        """Recalculate today's spending from the persisted usage log."""
        if not self.log_file:
            return
        if not self.log_file.exists():
            self.total, self.by_provider, self.calls = 0.0, {}, {}
            return

        try:
            lines = self.log_file.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            print(f"⚠️  Could not read {self.log_file.name}: {error}")
            return

        self.total, self.by_provider, self.calls = 0.0, {}, {}
        today = date.today().isoformat()
        skipped = 0
        for line in lines:
            try:
                entry = json.loads(line)
                if entry["time"][:10] == today:
                    self._add(entry["provider"], float(entry["cost"]))
            except (ValueError, KeyError, TypeError):
                # Ignore malformed entries, such as incomplete crash-time writes.
                skipped += 1
        if skipped:
            print(f"⚠️  Skipped {skipped} unreadable line(s) in {self.log_file.name}")


class RateLimiter:
    """Space requests to one provider by a minimum time interval."""

    def __init__(self, calls_per_minute):
        if calls_per_minute <= 0:
            raise ValueError("calls_per_minute must be greater than zero")
        self.min_interval = 60.0 / calls_per_minute
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Wait until this provider can receive the next request."""
        with self._lock:
            delay = self._last_call + self.min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last_call = time.monotonic()


def _is_retryable(error):
    """Identify transient network, timeout, rate-limit, and server failures."""
    if isinstance(error, (openai.APIConnectionError, httpx.TransportError)):
        return True
    return getattr(error, "status_code", None) in RETRYABLE_STATUS


def _build_messages(prompt, system=None):
    """Build the shared chat message format for both providers."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


class LLMProviders:
    """Call either provider with retries, optional fallback, and cost tracking."""

    def __init__(self, calls_per_minute=30, usage_log=USAGE_LOG):
        cfg = get_config()
        self.max_retries = cfg.max_retries
        if self.max_retries < 1:
            raise ValueError("max_retries must be at least one")

        # Disable SDK retries so this class controls every attempt and delay.
        self._openai = openai.OpenAI(
            api_key=cfg.openai_api_key, timeout=cfg.request_timeout, max_retries=0
        )
        self._cohere = cohere.ClientV2(
            api_key=cfg.cohere_api_key, timeout=cfg.request_timeout, max_retries=0
        )
        self.costs = CostTracker(cfg.daily_budget, log_file=usage_log)
        self._limiters = {
            "openai": RateLimiter(calls_per_minute),
            "cohere": RateLimiter(calls_per_minute),
        }

    def ask(self, provider, prompt, system=None, max_tokens=300, used_fallback=False):
        """Request an answer, retrying only failures likely to be temporary."""
        providers = {"openai": self._call_openai, "cohere": self._call_cohere}
        if provider not in providers:
            raise ValueError(f"Unsupported provider: {provider}")
        call = providers[provider]
        self.costs.check_budget()

        last_error = None
        for attempt in range(self.max_retries):
            self._limiters[provider].wait()
            try:
                answer, model, tokens_in, tokens_out = call(prompt, system, max_tokens)
            except Exception as error:
                last_error = error
                if not _is_retryable(error):
                    break
                if attempt < self.max_retries - 1:
                    # Exponential backoff reduces pressure during temporary failures.
                    time.sleep(2 ** attempt)
                continue

            response = LLMResponse(
                text=answer,
                provider=provider,
                model=model,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                cost=self.costs.calculate(model, tokens_in, tokens_out),
                used_fallback=used_fallback,
            )
            self.costs.record(response)
            return response

        raise LLMError(
            f"{provider} failed: {type(last_error).__name__}: {last_error}"
        )

    def ask_with_fallback(self, prompt, primary="openai", system=None, max_tokens=300):
        """Try the preferred provider, then the alternative if necessary."""
        if primary not in OTHER_PROVIDER:
            raise ValueError(f"Unsupported provider: {primary}")
        try:
            return self.ask(primary, prompt, system, max_tokens)
        except BudgetExceededError:
            # A shared exhausted budget also blocks the backup provider.
            raise
        except LLMError as primary_error:
            backup = OTHER_PROVIDER[primary]
            print(f"⚠️  {primary} failed, falling back to {backup}")
            try:
                return self.ask(backup, prompt, system, max_tokens, used_fallback=True)
            except LLMError as backup_error:
                raise LLMError(
                    f"All providers failed. {primary_error}; {backup_error}"
                ) from None

    def _call_openai(self, prompt, system, max_tokens):
        """Return OpenAI answer text, model, and token counts."""
        response = self._openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=_build_messages(prompt, system),
            max_tokens=max_tokens,
        )
        usage = response.usage
        return (
            response.choices[0].message.content.strip(),
            OPENAI_MODEL,
            usage.prompt_tokens,
            usage.completion_tokens,
        )

    def _call_cohere(self, prompt, system, max_tokens):
        """Return Cohere answer text, model, and billed token counts."""
        response = self._cohere.chat(
            model=COHERE_MODEL,
            messages=_build_messages(prompt, system),
            max_tokens=max_tokens,
        )
        tokens = response.usage.tokens
        return (
            response.message.content[0].text.strip(),
            COHERE_MODEL,
            int(tokens.input_tokens),
            int(tokens.output_tokens),
        )


if __name__ == "__main__":
    try:
        llm = LLMProviders()
        question = "In one sentence, what is an API?"

        for name in ("openai", "cohere"):
            answer = llm.ask(name, question, max_tokens=60)
            print(f"✅ {name} ({answer.model}): {answer.text}")
            print(
                f"   tokens in/out: {answer.input_tokens}/{answer.output_tokens}"
                f"  cost: ${answer.cost:.6f}\n"
            )

        answer = llm.ask_with_fallback(question, primary="openai", max_tokens=60)
        print(f"✅ fallback helper answered via {answer.provider}\n")
        print(llm.costs.summary())
    except (ValueError, LLMError) as error:
        print(f"❌ {error}")
        raise SystemExit(1)
