"""Load application settings from environment variables."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application configuration."""

    asknews_api_key: str = os.getenv("ASKNEWS_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    environment: str = os.getenv("ENVIRONMENT", "development")
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    daily_budget: float = float(os.getenv("DAILY_BUDGET", "5.00"))


settings = Settings()


def validate_settings() -> None:
    """Raise an error listing any required API keys that are missing."""
    required_keys = {
        "ASKNEWS_API_KEY": settings.asknews_api_key,
        "OPENAI_API_KEY": settings.openai_api_key,
        "COHERE_API_KEY": settings.cohere_api_key,
    }
    missing = [name for name, value in required_keys.items() if not value]

    if missing:
        raise ValueError(
            "Missing required configuration: " + ", ".join(missing)
        )


if __name__ == "__main__":
    validate_settings()
    print(f"Configuration valid for {settings.environment} environment.")