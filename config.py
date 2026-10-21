"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    openai_api_key: str = ""
    cohere_api_key: str = ""
    news_api_key: str = ""
    environment: str = "development"
    max_retries: int = 3
    request_timeout: int = 30
    daily_budget: float = 5.0

    def missing_keys(self) -> list[str]:
        """Return required API key names that have not been configured."""
        return [
            name
            for name, value in {
                "OPENAI_API_KEY": self.openai_api_key,
                "COHERE_API_KEY": self.cohere_api_key,
                "NEWS_API_KEY": self.news_api_key,
            }.items()
            if not value or value.startswith("<")
        ]


def get_config() -> Config:
    """Load the current configuration from `.env` and the process environment."""
    load_dotenv()
    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        cohere_api_key=os.getenv("COHERE_API_KEY", ""),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        environment=os.getenv("ENVIRONMENT", "development"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        daily_budget=float(os.getenv("DAILY_BUDGET", "5.00")),
    )


if __name__ == "__main__":
    config = get_config()
    missing = config.missing_keys()
    if missing:
        print(f"Missing configuration: {', '.join(missing)}")
    else:
        print("Configuration valid.")
