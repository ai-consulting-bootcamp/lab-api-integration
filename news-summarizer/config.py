"""Load settings and API keys from .env and check that nothing is missing."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

REQUIRED_KEYS = ["OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY"]


@dataclass
class Config:
    """All settings in one object. Use lowercase names everywhere."""
    openai_api_key: str
    cohere_api_key: str
    news_api_key: str
    environment: str = "development"
    max_retries: int = 3
    request_timeout: int = 30
    daily_budget: float = 5.00


def get_config() -> Config:
    """Read .env, stop with a clear message if a key is missing, return a Config."""
    missing = [key for key in REQUIRED_KEYS
               if not os.getenv(key) or os.getenv(key).startswith("<")]
    if missing:
        raise ValueError(
            f"[config] Missing required configuration: {', '.join(missing)}. "
            "Add them to news-summarizer/.env (no quotes, no spaces)."
        )

    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        cohere_api_key=os.getenv("COHERE_API_KEY"),
        news_api_key=os.getenv("NEWS_API_KEY"),
        environment=os.getenv("ENVIRONMENT", "development"),
        max_retries=int(os.getenv("MAX_RETRIES", 3)),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", 30)),
        daily_budget=float(os.getenv("DAILY_BUDGET", 5.00)),
    )


if __name__ == "__main__":
    config = get_config()
    print("✅ Configuration valid")
    print(f"   Environment:  {config.environment}")
    print(f"   Max retries:  {config.max_retries}")
    print(f"   Timeout:      {config.request_timeout}s")
    print(f"   Daily budget: ${config.daily_budget:.2f}")