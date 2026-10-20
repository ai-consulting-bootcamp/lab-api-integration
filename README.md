# Two brains, zero single point of failure

**Track:** Module 2 — API integration · **When:** Week 3, Day 2 · **Status:** Required

This repository contains everything you need for this lab.

## Files

- [`instructions.md`](./instructions.md) — the lab instructions
- [`rubric.md`](./rubric.md) — how your submission is graded; this is what the AI reviewer checks your PR against


# Multi-Provider News Summarizer

A Python command-line application that retrieves news articles using NewsAPI, generates summaries with OpenAI, and analyzes sentiment with Cohere.

The application demonstrates multi-provider API integration, fallback handling, retries, rate limiting, and estimated API cost tracking.

## Features

- Fetch news articles from seven categories using NewsAPI.
- Summarize articles with OpenAI (`gpt-4o-mini`).
- Analyze sentiment with Cohere (`command-a-03-2025`).
- Fall back to another LLM provider for supported temporary failures.
- Retry transient API errors with exponential backoff.
- Apply basic request rate limiting.
- Track estimated API costs against a configured budget.
- Interact through a command-line menu.

## Project Structure

```text
lab-api-integration/
├── config.py
├── news_api.py
├── llm_providers.py
├── summarizer.py
├── main.py
├── test_summarizer.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── lab_summary.md
└── lab_proof.md
```

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file using `.env.example` as a template and add your API credentials:

```env
OPENAI_API_KEY=your_key
COHERE_API_KEY=your_key
NEWS_API_KEY=your_key

ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

Never commit real API credentials to GitHub.

## Running the Application

```bash
python main.py
```

Select a news category and choose between one and five articles.

The application retrieves the articles and displays their titles, sources, summaries, sentiment analyses, and estimated API costs.

## Testing

Run the automated test suite:

```bash
pytest test_summarizer.py -v
```

**Latest test result:** 13 tests passed.

The tests cover article processing, error handling, provider fallback, retries, budget checks, and rate limiting. External API calls are mocked during testing.

## Example Execution

A successful test run processed three technology-category articles.

| Metric | Result |
|---|---|
| Articles processed | 3 |
| Successful summaries | 3 |
| Successful sentiment analyses | 3 |
| Total estimated API cost | $0.001954 |
| Configured budget | $5.00 |

The three articles received negative, positive, and neutral sentiment assessments.

## Architecture

```text
User
  ↓
main.py
  ↓
NewsSummarizer
  ├── NewsAPI → NewsAPI.org
  └── LLMProviders
       ├── OpenAI → Summarization
       └── Cohere → Sentiment analysis
  ↓
Results and estimated costs
```

OpenAI and Cohere provide fallback options for each other's assigned tasks when supported transient failures occur.

## Limitations

- The application uses article metadata and available content snippets, not necessarily full article text.
- NewsAPI categories may return articles that are only loosely related to the selected