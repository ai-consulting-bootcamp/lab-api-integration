"""Load and validate settings for the news summarizer."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Load the .env next to this file, regardless of the working directory.
load_dotenv(Path(__file__).with_name(".env"))

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

ARTICLE_COUNT = 3
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# All three services are required: news, summaries, and sentiment analysis.
if not NEWS_API_KEY:
    raise ValueError("NEWS_API_KEY fehlt in der .env-Datei.")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY fehlt in der .env-Datei.")

if not COHERE_API_KEY:
    raise ValueError("COHERE_API_KEY fehlt in der .env-Datei.")

if REQUEST_TIMEOUT <= 0:
    raise ValueError("REQUEST_TIMEOUT muss groesser als 0 sein.")
