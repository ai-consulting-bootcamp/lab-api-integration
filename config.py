
import os
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Application settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", 5.00))


def validate_config():
    """Check that all required API keys are configured."""

    missing_keys = []

    if not OPENAI_API_KEY:
        missing_keys.append("OPENAI_API_KEY")

    if not COHERE_API_KEY:
        missing_keys.append("COHERE_API_KEY")

    if not NEWS_API_KEY:
        missing_keys.append("NEWS_API_KEY")

    if missing_keys:
        print("Missing API keys:", ", ".join(missing_keys))
        return False

    print("Configuration valid! All API keys are present.")
    return True


if __name__ == "__main__":
    validate_config()
