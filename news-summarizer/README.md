# Technology News Summarizer

A command-line application that fetches US technology headlines from NewsAPI, summarizes each article, and analyzes the summary's sentiment. It uses OpenAI and Cohere, supports provider fallback, processes articles concurrently, and reports estimated LLM token costs for the current run.

## Features

- Fetches up to five US technology headlines from NewsAPI.
- Summarizes article titles, descriptions, and content with OpenAI.
- Analyzes summary sentiment with Cohere.
- Falls back to the other provider if the primary provider request fails.
- Processes articles asynchronously while preserving their input order.
- Reports provider token counts and estimated costs.
- Includes unit tests that use stub providers and do not make live API calls.

## Requirements

- Python 3.10 or later.
- API keys for NewsAPI, OpenAI, and Cohere.

## Setup

Open a terminal in the `news-summarizer` directory and install the dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in this directory with your own API keys:

```dotenv
NEWS_API_KEY=your_newsapi_key
OPENAI_API_KEY=your_openai_key
COHERE_API_KEY=your_cohere_key

ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

Do not commit `.env`; it is excluded by `.gitignore`. The application needs all three API keys. `DAILY_BUDGET` is an in-memory per-run LLM cost threshold, not a persistent daily usage tracker.

## Run the application

From the `news-summarizer` directory:

```bash
python main.py
```

Choose between one and five articles when prompted. Press Enter to use the default of three, or enter `q` to quit.

To validate configuration:

```bash
python config.py
```

To run the unit tests:

```bash
python -m pytest test_summarizer.py -v
```

## Example output

Article titles, summaries, and model responses change between runs. A run looks like:

```text
How many technology articles should I summarize? (1-5, default 3; q to quit): 2

1. Example technology headline
   Source: Example News
   Summary: A concise summary of the article's main facts.
   Sentiment: Neutral: the report is primarily factual.
   URL: https://example.com/article

2. Another technology headline
   Source: Example News
   Summary: A concise summary of the second article.
   Sentiment: Positive: the article describes a favorable development.
   URL: https://example.com/another-article

Usage and estimated cost:
  Cohere: 700 input tokens, 180 output tokens, estimated $0.000213
  OpenAI: 900 input tokens, 160 output tokens, estimated $0.000231
  Total estimated cost: $0.000444
```

The token counts and amounts above are illustrative; actual output depends on the fetched articles and generated responses.

## Cost analysis

The application records token usage reported by each LLM provider and estimates cost using the rates currently configured in `llm_providers.py`:

| Provider | Model | Input rate per 1 million tokens | Output rate per 1 million tokens |
| --- | --- | ---: | ---: |
| OpenAI | `gpt-4o-mini` | $0.15 | $0.60 |
| Cohere | `command-r-08-2024` | $0.15 | $0.60 |

For each request, the estimate is calculated as:

```text
(input tokens × input rate + output tokens × output rate) / 1,000,000
```

Typically, each article uses one summarization request and one sentiment request. A failed primary request may result in an additional fallback request. The estimates are based on the rates in this project's source code; confirm current provider pricing and update `llm_providers.py` if needed. NewsAPI usage is not included in the LLM cost summary.
