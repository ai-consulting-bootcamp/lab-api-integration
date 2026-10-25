
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")

    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "5.00"))


def validate_config():
    required_keys = {
        "OPENAI_API_KEY": Config.OPENAI_API_KEY,
        "ANTHROPIC_API_KEY": Config.ANTHROPIC_API_KEY,
        "NEWS_API_KEY": Config.NEWS_API_KEY,
    }

    missing_keys = [
        name for name, value in required_keys.items() if not value
    ]

    if missing_keys:
        raise ValueError(
            f"Missing required configuration: {', '.join(missing_keys)}"
        )

    print("Configuration validated successfully!")


if __name__ == "__main__":
    validate_config()
