# Multi-Provider News Summarizer

A Python app that fetches real news, has **OpenAI** write a short summary, has **Cohere** classify the sentiment of that summary, and **keeps working if one AI provider fails**.

```
News API  →  OpenAI (summary)  →  Cohere (sentiment)  →  result + cost report
                 ▲                      │
                 └──── fallback ────────┘
```

## Features
- **Two AI providers** with automatic fallback (no single point of failure)
- **Retries** with exponential backoff (1 s, 2 s, 4 s); no retry on authentication errors
- **Rate limiting** (at least 1 s between calls)
- **Cost tracking** per provider (input/output tokens) and a **daily budget** limit
- **Quality guards:** title-only articles are flagged, and numbers in a summary that are not in the source are flagged
- **17 unit tests** with a fake LLM (free, no network)

## Project structure
| File | Job |
|---|---|
| `config.py` | Loads settings and API keys from `.env`, stops with a clear message if a key is missing |
| `news_api.py` | Fetches top headlines from newsapi.org |
| `llm_providers.py` | OpenAI + Cohere clients, retries, fallback, rate limiting, cost tracking |
| `summarizer.py` | The workflow: summary → sentiment for each article |
| `test_summarizer.py` | Unit tests (pytest) |
| `main.py` | Interactive app |
| `lab_proof.md` | Proof for the reviewer: config, input, trace, output |

## Setup
1. Get three API keys: [OpenAI](https://platform.openai.com), [Cohere](https://dashboard.cohere.com), [News API](https://newsapi.org)
2. Create and activate an environment, then install:
```bash
   conda activate bootcamp-env
   pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and paste your keys (no quotes, no spaces). Never commit `.env`.

## How to run
```bash
python main.py                  # interactive app
pytest test_summarizer.py -v    # run the tests
```
Choose a category (e.g. `science`) and 1–5 articles. Results are saved to `output_<category>_<time>.json`.

## Example output
```
📰 'It was jaw-dropping': The shocking lessons from an infamous experiment in obedience - BBC  (BBC News)
   A recent analysis of obedience experiments reveals that a vast majority of participants are
   willing to follow authority figures, with only 2.6% of nearly 800 volunteers refusing ...
   Sentiment: negative
   Providers: summary=openai, sentiment=cohere

✅ Processed 3/3 articles
💰 Total calls: 6 | Total cost: $0.000133
  openai: 3 calls | input 292 tokens | output 132 tokens | $0.000123
  cohere: 3 calls | input 249 tokens | output 3 tokens | $0.000010
```

## Cost analysis
| | Run of 3 articles | Per article |
|---|---|---|
| OpenAI `gpt-4o-mini` (summary) | $0.000123 (~92%) | ~$0.000041 |
| Cohere `command-r7b` (sentiment) | $0.000010 (~8%) | ~$0.000003 |
| **Total** | **$0.000133** | **~$0.000044** |

- About **22,000 articles per $1**; the $5 daily budget is far above normal use.
- The **summary step** is ~92% of the cost, because it reads the article *and* writes a longer answer (output tokens cost 4× more than input for gpt-4o-mini).
- Token counts differ between providers (different tokenizers), so compare providers by **dollars**, not tokens. In my tests Cohere was about 3× cheaper for the same prompt.
- Ideas to reduce cost: cache already-processed articles, and skip articles that only have a title.

## Known limitations
- News API often returns articles with **no text** (title only), and the category filter is not always reliable.
- A fallback keeps the app **available**, but the backup model may **change quality** (it invented details for a title-only article in my tests).
- Summaries can contain facts that are not in the source; the number check catches numbers, not other claims.