# Two brains, zero single point of failure

## What the project does

The News Summarizer fetches current technology articles from NewsAPI. OpenAI
creates a concise summary for each article, and Cohere performs aspect-based
sentiment analysis (ABSA), identifying aspects such as products, companies,
security, users, or financial impact. The application also tracks token usage
and estimates the cost of each LLM request.

## Setup

From the repository root, install the dependencies:

```bash
cd news-summarizer
python3 -m pip install -r requirements.txt
```

Create or update `news-summarizer/.env` with your own keys. Never commit this
file:

```env
OPENAI_API_KEY=your_openai_key
COHERE_API_KEY=your_cohere_key
NEWS_API_KEY=your_newsapi_key

OPENAI_MODEL=gpt-4o-mini
COHERE_MODEL=command-a-03-2025
REQUEST_TIMEOUT=30
```

Validate the configuration:

```bash
python3 config.py
```

## How to run it

Run the interactive application from the `news-summarizer` directory:

```bash
python3 main.py
```

Enter a number from 1 to 5 when prompted. The application fetches that many
technology articles, summarizes them, analyzes sentiment by aspect, and then
prints a cost summary. Enter `q` to quit.

Run the unit tests with:

```bash
pytest test_summarize.py -v
```

## Example output

```text
Technology News Summarizer
OpenAI creates summaries; Cohere performs aspect-based sentiment analysis.

How many technology articles should be processed? (1-5, or q to quit): 2

1. New technology product announced
   Source: Example News
   Summary: The company announced a new product focused on enterprise users.
   Aspect-based sentiment:
      - Product: Positive, confidence=0.91
        Evidence: The product is expected to improve enterprise workflows.
      - Users: Neutral, confidence=0.74
        Evidence: The article does not report user feedback yet.

Cost summary:
- openai (gpt-4o-mini): 42 input + 28 output tokens = $0.000023
- cohere (command-a-03-2025): 55 input + 31 output tokens = $0.000074
Total estimated cost: $0.000097
```

## Cost analysis

The application calculates an estimate from the input and output token counts
returned by each provider:

```text
estimated cost =
  (input tokens × input price per million +
   output tokens × output price per million) / 1,000,000
```

The default rates are defined in `llm_providers.py` and can be overridden in
`.env` with `OPENAI_INPUT_COST_PER_MILLION`,
`OPENAI_OUTPUT_COST_PER_MILLION`, `COHERE_INPUT_COST_PER_MILLION`, and
`COHERE_OUTPUT_COST_PER_MILLION`. These are estimates; provider billing and
model pricing should be checked before production use.


