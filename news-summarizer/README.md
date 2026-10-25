# Multi-provider news summarizer

This application fetches technology headlines from NewsAPI, summarizes each article with OpenAI, analyzes the summary with Anthropic, and prints trending topics plus estimated provider cost.

## Setup

```bash
cd news-summarizer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `NEWS_API_KEY` in `.env`. Keep `.env` private.

## Run

```bash
python main.py
pytest test_summarizer.py -v
```

The test suite mocks both external APIs, so it does not spend credits. A live run prints each title, summary, sentiment, trending topics, and total estimated cost. If processing one article fails, the original description is retained and the sentiment is marked unavailable.

See [`lab_proof.md`](lab_proof.md) for the workflow mapping, input, trace, and output record.
