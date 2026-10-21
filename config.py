"""
config.py - Production configuration: validate the API keys and report which ones are missing.
"""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables (override=True: values in .env always win over
# old values already in the environment, e.g. inherited from the notebook kernel)
load_dotenv(override=True)

# Keys the lab needs in .env
REQUIRED_KEYS = ["OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY"]


class Config:
    """Configuration for different environments."""

    def __init__(self, environment: Optional[str] = None):
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "development")

        self.environment = environment
        self.load_config()

    def load_config(self):
        """Load configuration based on environment."""
        if self.environment == "production":
            self.debug = False
            self.max_retries = 5
            self.timeout = 60
            self.log_level = "INFO"
            self.use_cache = True
            self.openai_model = "gpt-4o"
            self.daily_budget = float(os.getenv("DAILY_BUDGET", "100.0"))

        elif self.environment == "staging":
            self.debug = True
            self.max_retries = 3
            self.timeout = 30
            self.log_level = "DEBUG"
            self.use_cache = True
            self.openai_model = "gpt-4o-mini"
            self.daily_budget = float(os.getenv("DAILY_BUDGET", "10.0"))

        else:  # development
            self.debug = True
            self.max_retries = 2
            self.timeout = 10
            self.log_level = "DEBUG"
            self.use_cache = False
            self.openai_model = "gpt-4o-mini"
            self.daily_budget = float(os.getenv("DAILY_BUDGET", "1.0"))

        # Lab .env values (MAX_RETRIES, REQUEST_TIMEOUT) override the environment defaults
        self.max_retries = int(os.getenv("MAX_RETRIES", self.max_retries))
        self.timeout = int(os.getenv("REQUEST_TIMEOUT", self.timeout))

        # Cohere model used for sentiment analysis (replaces Anthropic from the training).
        # Override with COHERE_MODEL in .env if needed.
        self.cohere_model = os.getenv("COHERE_MODEL", "command-r-08-2024")

    def validate(self) -> bool:
        """
        Check that all required API keys are set.

        Returns:
            True if all keys are present

        Raises:
            ValueError: naming every missing key
        """
        missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        return True

    def get_budget_manager(self):
        """Get configured budget manager."""
        # Imported here to avoid a circular import (llm_providers imports config)
        from llm_providers import TokenBudgetManager
        return TokenBudgetManager(daily_budget=self.daily_budget)


if __name__ == "__main__":
    # Checkpoint 1: validate configuration
    config = Config()
    try:
        config.validate()
        print("✅ Configuration valid - all API keys found")
    except ValueError as e:
        print(f"❌ {e}")

    # Usage (training)
    print(f"Environment: {config.environment}")
    print(f"Debug mode: {config.debug}")
    print(f"Using model: {config.openai_model} (OpenAI), {config.cohere_model} (Cohere)")
    print(f"Max retries: {config.max_retries}")
    print(f"Timeout: {config.timeout}s")
    print(f"Daily budget: ${config.daily_budget:.2f}")
