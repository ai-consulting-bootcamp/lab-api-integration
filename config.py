
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    openai_api_key: str
    cohere_api_key: str
    news_api_key: str
    environment: str
    max_retries: int
    request_timeout: int
    daily_budget: float

    def validate(self):
        """Check that all required API keys are present."""
        missing = []

        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.cohere_api_key:
            missing.append("COHERE_API_KEY")
        if not self.news_api_key:
            missing.append("NEWS_API_KEY")

        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}"
            )

        if self.max_retries < 0:
            raise ValueError("MAX_RETRIES cannot be negative")
        if self.request_timeout <= 0:
            raise ValueError("REQUEST_TIMEOUT must be positive")
        if self.daily_budget <= 0:
            raise ValueError("DAILY_BUDGET must be positive")


def get_config() -> Config:
    """Load and validate configuration."""
    config = Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        cohere_api_key=os.getenv("COHERE_API_KEY", ""),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        environment=os.getenv("ENVIRONMENT", "development"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        daily_budget=float(os.getenv("DAILY_BUDGET", "5.00")),
    )

    config.validate()
    return config


if __name__ == "__main__":
    try:
        config = get_config()
        print("Configuration validated successfully!")
        print(f"Environment: {config.environment}")
        print(f"Max retries: {config.max_retries}")
        print(f"Request timeout: {config.request_timeout}s")
        print(f"Daily budget: ${config.daily_budget:.2f}")
        print("All 3 API keys are configured.")

    except ValueError as error:
        print(f"Configuration error: {error}")
        raise SystemExit(1)
