import os

from dotenv import load_dotenv

load_dotenv()

required_keys = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NEWS_API_KEY",
]

missing_keys = [key for key in required_keys if not os.getenv(key)]

if missing_keys:
    raise ValueError(
        "Missing environment variables: " + ", ".join(missing_keys)
    )

print("Configuration validated. Required API keys are available.")
