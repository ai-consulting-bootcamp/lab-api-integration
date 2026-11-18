"""Configuration module: loads settings from .env and validates them."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Central place for all settings used by the app."""

    # API keys (required)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")

    # App settings (with safe defaults)
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", "5.00"))

    # Models (override in .env if a model name changes)
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    COHERE_MODEL = os.getenv("COHERE_MODEL", "command-a-03-2025")

    @classmethod
    def validate(cls):
        """Raise ValueError listing any missing or placeholder API keys."""
        required = {
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "COHERE_API_KEY": cls.COHERE_API_KEY,
            "NEWS_API_KEY": cls.NEWS_API_KEY,
        }
        missing = [
            name for name, value in required.items()
            if not value or value.startswith("<")
        ]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}"
            )
        return True


if __name__ == "__main__":
    try:
        Config.validate()
        print("✓ Configuration is valid")
        print(f"  Environment:  {Config.ENVIRONMENT}")
        print(f"  Daily budget: ${Config.DAILY_BUDGET:.2f}")
        print(f"  Models:       {Config.OPENAI_MODEL} / {Config.COHERE_MODEL}")
    except ValueError as error:
        print(f"✗ {error}")