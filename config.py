import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class Config:
    """Configuration for the Multi-Provider News Summarizer."""

    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")

        # API keys
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.cohere_api_key = os.getenv("COHERE_API_KEY")
        self.news_api_key = os.getenv("NEWS_API_KEY")

        # General settings
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        self.daily_budget = float(os.getenv("DAILY_BUDGET", "5.00"))

    def validate(self):
        """Check whether all required API keys are configured."""

        missing_keys = []

        if not self.openai_api_key:
            missing_keys.append("OPENAI_API_KEY")

        if not self.cohere_api_key:
            missing_keys.append("COHERE_API_KEY")

        if not self.news_api_key:
            missing_keys.append("NEWS_API_KEY")

        if missing_keys:
            print("Missing environment variables:")
            for key in missing_keys:
                print(f"- {key}")
            return False

        print("Configuration validated successfully!")
        return True


if __name__ == "__main__":
    config = Config()

    print(f"Environment: {config.environment}")
    print(f"Max retries: {config.max_retries}")
    print(f"Request timeout: {config.timeout}")
    print(f"Daily budget: ${config.daily_budget:.2f}")

    config.validate()