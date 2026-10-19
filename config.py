import os
from dotenv import load_dotenv

# Load environment variables from the .env file into memory
load_dotenv()

class Config:
    """Centralized configuration for the News Summarizer pipeline."""
    
    # API Keys)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COHERE_API_KEY = os.getenv("COHERE_API_KEY") 
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    
    # Operational Thresholds (Casting strings from .env into ints/floats)
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))
    DAILY_BUDGET = float(os.getenv("DAILY_BUDGET", 5.00))

    @classmethod
    def validate(cls):
        """Validates that all critical API keys are present and correctly formatted."""
        critical_keys = {
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "COHERE_API_KEY": cls.COHERE_API_KEY,
            "NEWS_API_KEY": cls.NEWS_API_KEY
        }
        
        missing_or_invalid = []
        for name, value in critical_keys.items():
            # Catch completely missing keys or ones that still have the template text
            if not value or value.strip() == "" or "<your key>" in value:
                missing_or_invalid.append(name)
                
        if missing_or_invalid:
            raise ValueError(f"Missing required configuration for: {', '.join(missing_or_invalid)}. Please check your .env file.")

def get_config():
    """Validates and returns the configuration object."""
    Config.validate()
    return Config

# Checkpoint 1: Run this file directly to test the environment loading
if __name__ == "__main__":
    try:
        cfg = get_config()
        print("✅ Checkpoint 1 passed! All API keys and settings loaded correctly.")
        print(f"Running in {cfg.ENVIRONMENT} mode with a max budget of ${cfg.DAILY_BUDGET}")
    except Exception as e:
        print(f"❌ Configuration Error: {e}")