
# Multi-Provider News Summarizer

A Python application that fetches technology news and uses multiple AI providers to summarize articles and analyze sentiment.

## Features

- Fetches technology news using NewsAPI
- Summarizes articles using OpenAI GPT-4o-mini
- Analyzes sentiment using Cohere Command A
- Falls back to Cohere if OpenAI summarization fails
- Retries temporary API failures
- Tracks estimated API token costs
- Records daily estimated spending
- Blocks new requests after the daily budget is reached
- Supports processing 1–5 articles
- Includes automated tests

## Setup

Requires Python 3.11 or later.

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file using `.env.example` as a template.

Configure:

- `OPENAI_API_KEY`
- `COHERE_API_KEY`
- `NEWS_API_KEY`

Never commit real API keys.

## Run

```bash
python main.py
```

Enter the number of articles to process.

## Tests

```bash
python -m pytest -v
```

## Architecture

NewsAPI retrieves articles.

OpenAI generates summaries.

Cohere performs sentiment analysis and serves as the fallback summarization provider.

The application estimates token costs and records daily spending locally.

## Limitations

- NewsAPI may return truncated article content.
- Cost tracking uses configured pricing estimates.
- Budget enforcement is a soft limit, not a guaranteed spending cap.
- API errors without HTTP status codes may still trigger retries.
- The current retry and fallback tests do not cover every failure scenario.
