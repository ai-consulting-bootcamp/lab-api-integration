"""Load and validate configuration for the news summarizer."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip()
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "5.00"))


def validate_config() -> bool:
    """Report missing API keys and return whether configuration is complete."""
    required_keys = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "COHERE_API_KEY": COHERE_API_KEY,
        "NEWS_API_KEY": NEWS_API_KEY,
    }
    missing_keys = [name for name, value in required_keys.items() if not value]

    if missing_keys:
        print("Missing required environment variable(s): " + ", ".join(missing_keys))
        print("Add them to the .env file in the news-summarizer directory.")
        return False

    print("Configuration validated successfully.")
    return True


if __name__ == "__main__":
    sys.exit(0 if validate_config() else 1)