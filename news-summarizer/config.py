"""Configuration for the news summarizer.

Reads settings from the .env file (or the environment) and checks that the
required API keys are present. Run `python config.py` to validate your setup.
"""
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

# Keys the app cannot run without.
REQUIRED_KEYS = ("OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY")


def _read_number(name: str, default: float, cast=float):
    """Read a number from the environment, falling back to a default if it is missing or invalid."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        print(f"Warning: {name}={raw!r} is not a valid number, using {default}")
        return default


class Config:
    """Holds every setting the app needs, in one place."""

    def __init__(self) -> None:
        # API keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.cohere_api_key = os.getenv("COHERE_API_KEY", "")
        self.news_api_key = os.getenv("NEWS_API_KEY", "")

        # Environment: development, staging or production
        self.environment = os.getenv("ENVIRONMENT", "development").lower()
        self.log_level = "INFO" if self.environment == "production" else "DEBUG"

        # Behaviour
        self.max_retries = _read_number("MAX_RETRIES", 3, int)
        self.request_timeout = _read_number("REQUEST_TIMEOUT", 30, int)
        self.daily_budget = _read_number("DAILY_BUDGET", 5.00, float)

        # Models live here, in one place. Override them in .env if one is retired.
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.cohere_model = os.getenv("COHERE_MODEL", "command-a-03-2025")

    def missing_keys(self) -> List[str]:
        """Return the names of required keys that are empty or still contain the template text."""
        values = {
            "OPENAI_API_KEY": self.openai_api_key,
            "COHERE_API_KEY": self.cohere_api_key,
            "NEWS_API_KEY": self.news_api_key,
        }
        return [name for name in REQUIRED_KEYS
                if not values[name] or values[name].startswith("<")]

    def validate(self) -> bool:
        """Return True if all required keys are set."""
        return not self.missing_keys()

    def summary(self) -> str:
        """Return a printable summary of the settings. Keys are never printed."""
        return (
            f"Environment:     {self.environment}\n"
            f"Log level:       {self.log_level}\n"
            f"Max retries:     {self.max_retries}\n"
            f"Request timeout: {self.request_timeout}s\n"
            f"Daily budget:    ${self.daily_budget:.2f}\n"
            f"OpenAI model:    {self.openai_model}\n"
            f"Cohere model:     {self.cohere_model}"
        )


def get_config() -> Config:
    """Create a Config from the current environment."""
    return Config()


if __name__ == "__main__":
    config = get_config()
    missing = config.missing_keys()
    if missing:
        print("❌ Missing required configuration:")
        for name in missing:
            print(f"   - {name}")
        print("Add them to your .env file (see .env.example).")
        sys.exit(1)
    print("✅ Configuration is valid")
    print(config.summary())
