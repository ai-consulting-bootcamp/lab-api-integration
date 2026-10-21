"""
llm_providers.py - OpenAI + Cohere with budget tracking, retry, circuit breaker and fallback.
RateLimiter ("Respects rate limits"), and ProductionAPIClient /ask_with_fallback generalised so either provider can be the primary.
"""

import os
import random
import time
from typing import Any, Callable, Dict, Optional

import cohere
from openai import OpenAI

from config import Config

config = Config()

# unit tests; config.validate() is what reports missing keys)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "not-set"), timeout=config.timeout)
cohere_client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY", "not-set"),
                                timeout=config.timeout)

# Default models
OPENAI_MODEL = config.openai_model
COHERE_MODEL = config.cohere_model


# --------------
# Rate limiting 
# --------------

class RateLimiter:
    """Keep a minimum interval between requests to stay under a requests-per-minute limit."""

    def __init__(self, requests_per_minute: int = 50):
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0

    def wait(self):
        """Sleep if the previous request was too recent."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()


rate_limiters = {
    "openai": RateLimiter(requests_per_minute=50),
    "cohere": RateLimiter(requests_per_minute=10),  # Cohere trial keys have low limits
}


# ------------------------------
# 1. Provider helper functions 
# ------------------------------

def ask_openai(prompt: str, model: str = OPENAI_MODEL) -> Dict[str, Any]:
    """
    Ask OpenAI a question and return response with usage data.

    Args:
        prompt: Question or instruction
        model: Model to use

    Returns:
        Dictionary with response text and usage information
    """
    rate_limiters["openai"].wait()
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract usage data directly from API response
    usage = response.usage

    return {
        "response": response.choices[0].message.content,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens
        }
    }


def ask_cohere(prompt: str, model: str = COHERE_MODEL) -> Dict[str, Any]:
    """
    Ask Cohere a question and return response with usage data.
    Same structure as the training's ask_anthropic.

    Args:
        prompt: Question or instruction
        model: Model to use

    Returns:
        Dictionary with response text and usage information
    """
    rate_limiters["cohere"].wait()
    response = cohere_client.chat(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract usage data directly from API response (billed tokens)
    usage = response.usage.billed_units

    return {
        "response": response.message.content[0].text,
        "usage": {
            "input_tokens": int(usage.input_tokens or 0),
            "output_tokens": int(usage.output_tokens or 0)
        }
    }


# -------------------------------
# 3. Token budget manager 
# -------------------------------

class TokenBudgetManager:
    """Manage token budgets using direct API usage data."""

    def __init__(self, daily_budget: float = 100.0):
        """
        Initialize token budget manager.

        Args:
            daily_budget: Daily budget in dollars
        """
        self.daily_budget = daily_budget
        self.used_budget = 0.0
        self.provider_usage = {
            "openai": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
            "cohere": {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        }

        # Pricing per 1M tokens (training OpenAI values; Cohere replaces Anthropic).
        # Check current prices on the provider pricing pages before submitting.
        self.pricing = {
            "openai": {
                "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
                "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000}
            },
            "cohere": {
                "command-r-08-2024": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000}
            }
        }

    def calculate_cost(self, provider: str, model: str, input_tokens: int,
                       output_tokens: int) -> float:
        """
        Calculate cost for a request using exact token counts.

        Args:
            provider: Provider name ("openai" or "cohere")
            model: Model name
            input_tokens: Number of input tokens (from API response)
            output_tokens: Number of output tokens (from API response)

        Returns:
            Cost in dollars (0.0 if the model has no pricing entry)
        """
        if provider not in self.pricing:
            return 0.0

        if model not in self.pricing[provider]:
            return 0.0

        pricing = self.pricing[provider][model]
        input_cost = input_tokens * pricing["input"]
        output_cost = output_tokens * pricing["output"]
        return input_cost + output_cost

    def track_request(self, provider: str, model: str, input_tokens: int,
                      output_tokens: int) -> Dict[str, Any]:
        """
        Track a request using exact token counts from API response.

        Args:
            provider: Provider name
            model: Model name
            input_tokens: Exact input tokens from API response
            output_tokens: Exact output tokens from API response

        Returns:
            Dictionary with cost and budget status
        """
        cost = self.calculate_cost(provider, model, input_tokens, output_tokens)

        # Check if we're over budget
        if self.used_budget + cost > self.daily_budget:
            remaining = self.daily_budget - self.used_budget
            raise Exception(
                f"Token budget exceeded! "
                f"Request cost ${cost:.6f}, but only ${remaining:.6f} remaining. "
                f"Daily budget: ${self.daily_budget:.2f}"
            )

        # Update usage with exact counts
        self.used_budget += cost
        if provider in self.provider_usage:
            self.provider_usage[provider]["input_tokens"] += input_tokens
            self.provider_usage[provider]["output_tokens"] += output_tokens
            self.provider_usage[provider]["cost"] += cost

        return {
            "cost": cost,
            "remaining_budget": self.daily_budget - self.used_budget,
            "budget_used_percent": (self.used_budget / self.daily_budget) * 100
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get budget summary."""
        return {
            "daily_budget": self.daily_budget,
            "used_budget": self.used_budget,
            "remaining_budget": self.daily_budget - self.used_budget,
            "budget_used_percent": (self.used_budget / self.daily_budget) * 100,
            "provider_usage": self.provider_usage
        }

    def print_summary(self):
        """Print budget summary."""
        summary = self.get_summary()
        print("\n" + "=" * 60)
        print("TOKEN BUDGET SUMMARY")
        print("=" * 60)
        print(f"Daily Budget: ${summary['daily_budget']:.2f}")
        print(f"Used: ${summary['used_budget']:.4f} ({summary['budget_used_percent']:.1f}%)")
        print(f"Remaining: ${summary['remaining_budget']:.4f}")
        print("\nProvider Breakdown:")
        for provider, usage in summary['provider_usage'].items():
            if usage['input_tokens'] > 0 or usage['output_tokens'] > 0:
                print(f"\n  {provider.upper()}:")
                print(f"    Input tokens: {usage['input_tokens']:,}")
                print(f"    Output tokens: {usage['output_tokens']:,}")
                print(f"    Total cost: ${usage['cost']:.4f}")
        print("=" * 60)


def ask_openai_with_budget(
    prompt: str,
    model: str = OPENAI_MODEL,
    budget_manager: TokenBudgetManager = None
) -> Dict[str, Any]:
    """
    Ask OpenAI with token budget tracking using DIRECT API usage data.

    Args:
        prompt: Question to ask
        model: Model to use
        budget_manager: TokenBudgetManager instance

    Returns:
        Dictionary with response and budget info
    """
    # Make API call - get response with usage data
    result = ask_openai(prompt, model)

    # Extract exact token counts from API response
    input_tokens = result['usage']['prompt_tokens']
    output_tokens = result['usage']['completion_tokens']

    # Track with budget manager using exact counts
    if budget_manager:
        budget_info = budget_manager.track_request(
            provider="openai",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        print(f"💰 Tokens: {input_tokens} input + {output_tokens} output = "
              f"{result['usage']['total_tokens']} total")
        print(f"   Cost: ${budget_info['cost']:.6f} (${budget_info['remaining_budget']:.4f} remaining)")

    return {
        "response": result['response'],
        "usage": result['usage'],
        "provider": "openai",
        "model": model
    }


def ask_cohere_with_budget(
    prompt: str,
    model: str = COHERE_MODEL,
    budget_manager: TokenBudgetManager = None
) -> Dict[str, Any]:
    """
    Ask Cohere with token budget tracking using DIRECT API usage data.

    Args:
        prompt: Question to ask
        model: Model to use
        budget_manager: TokenBudgetManager instance

    Returns:
        Dictionary with response and budget info
    """
    # Make API call - get response with usage data
    result = ask_cohere(prompt, model)

    # Extract exact token counts from API response
    input_tokens = result['usage']['input_tokens']
    output_tokens = result['usage']['output_tokens']

    # Track with budget manager using exact counts
    if budget_manager:
        budget_info = budget_manager.track_request(
            provider="cohere",
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        print(f"💰 Tokens: {input_tokens} input + {output_tokens} output")
        print(f"   Cost: ${budget_info['cost']:.6f} (${budget_info['remaining_budget']:.4f} remaining)")

    return {
        "response": result['response'],
        "usage": result['usage'],
        "provider": "cohere",
        "model": model
    }


# -----------------
# Failure handling 
# -----------------

def exponential_backoff_with_jitter(attempt, base_delay=1, max_delay=60):
    """
    Calculate backoff time with jitter.

    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Wait time in seconds with jitter applied
    """
    # Calculate exponential delay: base_delay * (2 ^ attempt)
    delay = base_delay * (2 ** attempt)

    # Cap at max_delay
    delay = min(delay, max_delay)

    # Add jitter: random value between 0 and delay
    # This spreads out retries so they don't all happen at once
    jittered_delay = delay * random.random()

    return jittered_delay


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold=5, timeout=60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before trying again (half-open state)
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
        self.success_count = 0  # Track successes in half-open state

    def call(self, func):
        """
        Call a function through the circuit breaker.

        Args:
            func: Function to call

        Returns:
            Function result
        """
        # Check if we should try again after being open
        if self.state == 'open':
            if time.time() - self.last_failure_time >= self.timeout:
                print("🔄 Circuit half-open, trying one request...")
                self.state = 'half_open'
            else:
                remaining = self.timeout - (time.time() - self.last_failure_time)
                raise Exception(
                    f"Circuit breaker is OPEN - failing fast. "
                    f"Try again in {remaining:.1f} seconds."
                )

        try:
            result = func()

            # Success! Reset the circuit breaker
            if self.state == 'half_open':
                print("✅ Request succeeded, closing circuit")

            self.failure_count = 0
            self.state = 'closed'
            return result

        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                print(f"\n🔴 Circuit breaker OPEN after {self.failure_count} failures")
                print(f"   State: {self.state} → OPEN")
                print(f"   Will try again in {self.timeout} seconds")
                self.state = 'open'

            raise

    def get_status(self):
        """Get current circuit breaker status."""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'threshold': self.failure_threshold
        }


def is_budget_error(error: Exception) -> bool:
    """True if the error comes from TokenBudgetManager (retrying will not fix it)."""
    return "Token budget exceeded" in str(error)


class ProductionAPIClient:
    """
    Production-ready API client with circuit breaker and jittered retry.

    Adapted from training: takes the provider function (api_func) as a parameter
    instead of a hard-coded OpenAI call, so OpenAI and Cohere each get one.
    """

    def __init__(
        self,
        api_func: Callable[[str], Dict[str, Any]],
        failure_threshold=5,
        circuit_timeout=60,
        max_retries=3,
        base_delay=1.0,
        max_delay=60.0
    ):
        self.api_func = api_func
        self.circuit_breaker = CircuitBreaker(failure_threshold, circuit_timeout)
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def call(self, prompt: str) -> Dict[str, Any]:
        """
        Call the provider with circuit breaker and jittered retry.

        Args:
            prompt: The prompt to send

        Returns:
            The provider result dictionary
        """
        def api_call():
            return self.api_func(prompt)

        # First, try through circuit breaker
        try:
            return self.circuit_breaker.call(api_call)
        except Exception as e:
            # If circuit is open, fail fast (don't retry)
            if self.circuit_breaker.state == 'open':
                raise Exception(f"Circuit breaker is open: {e}")

            # Budget errors are not transient: do not retry them
            if is_budget_error(e):
                raise

            # If circuit is closed but call failed, retry with jitter
            # (This handles transient failures)
            for attempt in range(self.max_retries):
                wait_time = exponential_backoff_with_jitter(
                    attempt, self.base_delay, self.max_delay
                )

                print(f"  ⚠️  Retry {attempt + 1}/{self.max_retries} in {wait_time:.2f}s...")
                time.sleep(wait_time)

                try:
                    return self.circuit_breaker.call(api_call)
                except Exception as retry_error:
                    if attempt == self.max_retries - 1 or is_budget_error(retry_error):
                        raise retry_error
                    continue

            raise

    def get_status(self):
        """Get current status of circuit breaker."""
        return self.circuit_breaker.get_status()


# ---------------------
# 2. Provider fallback 
# ---------------------

PROVIDER_NAMES = {"openai": "OpenAI", "cohere": "Cohere"}


class LLMProviders:
    """Both providers behind ProductionAPIClient, sharing one TokenBudgetManager."""

    def __init__(self, budget_manager: Optional[TokenBudgetManager] = None,
                 max_retries: int = config.max_retries):
        """
        Args:
            budget_manager: Shared TokenBudgetManager (from Config if not given)
            max_retries: Retries per provider before falling back
        """
        self.budget_manager = budget_manager or config.get_budget_manager()
        self.clients = {
            "openai": ProductionAPIClient(
                lambda p: ask_openai_with_budget(p, budget_manager=self.budget_manager),
                failure_threshold=3, circuit_timeout=30, max_retries=max_retries
            ),
            "cohere": ProductionAPIClient(
                lambda p: ask_cohere_with_budget(p, budget_manager=self.budget_manager),
                failure_threshold=3, circuit_timeout=30, max_retries=max_retries
            ),
        }

    def ask_with_fallback(self, prompt: str, primary: str = "openai",
                          secondary: str = "cohere") -> Dict[str, Any]:
        """
        Try primary provider first, fall back to secondary if it fails.
        Returns usage data from whichever provider succeeded.

        Args:
            prompt: Question to ask
            primary: Primary provider to try first
            secondary: Backup provider

        Returns:
            Response and usage data from whichever provider succeeded
        """
        # Try primary provider
        try:
            print(f"Trying {PROVIDER_NAMES[primary]} (primary)...")
            result = self.clients[primary].call(prompt)
            print(f"✓ {PROVIDER_NAMES[primary]} succeeded")
            return {
                "provider": primary,
                "model": result["model"],
                "response": result["response"],
                "usage": result["usage"],
                "fallback_used": False
            }

        except Exception as e:
            print(f"✗ {PROVIDER_NAMES[primary]} failed: {e}")
            print(f"Falling back to {secondary}...")

        # If primary failed, try secondary
        try:
            print(f"Trying {PROVIDER_NAMES[secondary]} (fallback)...")
            result = self.clients[secondary].call(prompt)
            print(f"✓ {PROVIDER_NAMES[secondary]} succeeded")
            return {
                "provider": secondary,
                "model": result["model"],
                "response": result["response"],
                "usage": result["usage"],
                "fallback_used": True
            }

        except Exception as e:
            print(f"✗ {PROVIDER_NAMES[secondary]} also failed: {e}")
            raise Exception("All providers failed")


if __name__ == "__main__":
    # Checkpoint 3: test both providers and show cost tracking
    config.validate()
    providers = LLMProviders()
    prompt = "Explain machine learning in one sentence"

    print("--- Test 1: OpenAI ---")
    result = providers.ask_with_fallback(prompt, primary="openai", secondary="cohere")
    print(f"Response: {result['response']}\n")

    print("--- Test 2: Cohere ---")
    result = providers.ask_with_fallback(prompt, primary="cohere", secondary="openai")
    print(f"Response: {result['response']}")

    providers.budget_manager.print_summary()
