from openai import OpenAI, APIConnectionError, RateLimitError, InternalServerError
import cohere
from config import Config

class TokenBudgetManager:
    """Manage token usage and costs across LLM providers."""

    def __init__(self, daily_budget: float = 5.0):

        self.daily_budget = daily_budget
        self.used_budget = 0.0

        self.provider_usage = {
            "openai": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            },
            "cohere": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0
            }
        }

        # Pricing per 1 million tokens (USD)
        self.pricing = {
            "openai": {
                "gpt-4o-mini": {
                    "input": 0.15,
                    "output": 0.60
                }
            },
            "cohere": {
                "command-r7b-12-2024": {
                    "input": 0.0375,
                    "output": 0.15
                }
            }
        }

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate API cost using actual token counts."""

        if provider not in self.pricing:
            raise ValueError(f"Unknown provider: {provider}")

        if model not in self.pricing[provider]:
            raise ValueError(f"Unknown model: {model}")

        pricing = self.pricing[provider][model]

        input_cost = (
            input_tokens * pricing["input"] / 1_000_000
        )

        output_cost = (
            output_tokens * pricing["output"] / 1_000_000
        )

        return input_cost + output_cost    

    def track_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> dict:
        """Track token usage and costs for an API request."""

        # Calculate request cost
        cost = self.calculate_cost(
            provider, model, input_tokens, output_tokens
        )

        # Check remaining budget
        if self.used_budget + cost > self.daily_budget:
            remaining = self.daily_budget - self.used_budget
            raise ValueError(
                f"Budget exceeded! "
                f"Request cost: ${cost:.6f}, "
                f"Remaining: ${remaining:.6f}"
            )

        # Update total budget usage
        self.used_budget += cost

        # Update provider-specific usage
        self.provider_usage[provider]["input_tokens"] += input_tokens
        self.provider_usage[provider]["output_tokens"] += output_tokens
        self.provider_usage[provider]["cost"] += cost

        # Return budget information
        return {
            "cost": cost,
            "remaining_budget": self.daily_budget - self.used_budget,
            "budget_used_percent": (
                self.used_budget / self.daily_budget
            ) * 100
        }

    def get_summary(self) -> dict:
        """Return current budget and provider usage summary."""

        return {
            "daily_budget": self.daily_budget,
            "used_budget": self.used_budget,
            "remaining_budget": self.daily_budget - self.used_budget,
            "budget_used_percent": (
                self.used_budget / self.daily_budget
            ) * 100,
            "provider_usage": self.provider_usage
        }

class LLMProviders:
    """Manage OpenAI and Cohere API clients."""

    def __init__(self):
        # Load configuration
        self.config = Config()
        self.budget_manager = TokenBudgetManager(daily_budget=self.config.daily_budget)

        # Check required API keys
        if not self.config.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing.")

        if not self.config.cohere_api_key:
            raise ValueError("COHERE_API_KEY is missing.")

        # Initialize OpenAI client
        self.openai_client = OpenAI(
            api_key=self.config.openai_api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries
        )

        # Initialize Cohere client
        self.cohere_client = cohere.ClientV2(
            api_key=self.config.cohere_api_key,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries
        )

    def ask_openai(self, prompt: str, model: str = "gpt-4o-mini") -> dict:
        """Send a prompt to OpenAI and return response with usage data."""

        response = self.openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract token usage
        usage = response.usage

        # Track OpenAI token usage and costs
        self.budget_manager.track_request(
            provider="openai",
            model=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens
        )

        return {
            "provider": "openai",
            "model": model,
            "response": response.choices[0].message.content,
            "usage": {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }
        }

    def ask_cohere(self, prompt: str, model: str = "command-r7b-12-2024") -> dict:
        """Send a prompt to Cohere and return response with usage data."""

        response = self.cohere_client.chat(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract token usage
        usage = response.usage

        # Track Cohere billable token usage and costs
        self.budget_manager.track_request(
            provider="cohere",
            model=model,
            input_tokens=usage.billed_units.input_tokens,
            output_tokens=usage.billed_units.output_tokens
        )

        return {
            "provider": "cohere",
            "model": model,
            "response": response.message.content[0].text,
            "usage": {
                "input_tokens": usage.tokens.input_tokens,
                "output_tokens": usage.tokens.output_tokens,
                "total_tokens": (
                    usage.tokens.input_tokens +
                    usage.tokens.output_tokens
                )
            },
            "billed_usage": {
                "input_tokens": usage.billed_units.input_tokens,
                "output_tokens": usage.billed_units.output_tokens
            }
        }

    def ask_with_fallback(self, prompt: str) -> dict:
        """Try OpenAI first and fall back to Cohere if needed."""

        try:
            print("Trying OpenAI (primary)...")
            return self.ask_openai(prompt)

        except (APIConnectionError, RateLimitError, InternalServerError) as e:
            print(f"OpenAI failed: {e}")
            print("Falling back to Cohere...")
            return self.ask_cohere(prompt)

if __name__ == "__main__":
    providers = LLMProviders()
    prompt = "Explain artificial intelligence in one sentence."

    # Test both LLM providers
    for name, ask_function in [
        ("OpenAI", providers.ask_openai),
        ("Cohere", providers.ask_cohere)
    ]:
        try:
            result = ask_function(prompt)

            print(f"\n{name} Response:")
            print(result["response"])
            print(f"Token usage: {result['usage']}")

        except Exception as e:
            print(f"{name} failed: {e}")

    # Display combined cost tracking
    print("\nBudget Summary:")
    print(providers.budget_manager.get_summary())