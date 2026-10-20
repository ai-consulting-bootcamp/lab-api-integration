# News Summarizer

Command-line application that fetches technology news, summarizes it in Spanish and classifies its sentiment using two LLM providers (OpenAI and Cohere), with retries, automatic fallback and cost control.

## What it does
1. Requests headlines from **NewsAPI**.
2. Summarizes each article in 2 sentences (OpenAI; Cohere if it fails).
3. Classifies sentiment: positive, neutral or negative (Cohere; OpenAI if it fails).
4. Prints the result, the provider used and the cost of every call.

## Files
| File | Responsibility |
|---|---|
| `config.py` | Reads `.env`, validates keys and settings |
| `news_api.py` | Fetches and cleans news articles |
| `llm_providers.py` | OpenAI/Cohere calls, retries, fallback and cost tracking |
| `summarizer.py` | Prompt templates, summary, sentiment, duplicate removal |
| `main.py` | Interactive application |
| `test_summarizer.py` | 14 tests using mocks (they cost no money) |

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env      # on Windows: copy .env.example .env
```
Fill in your `OPENAI_API_KEY`, `COHERE_API_KEY` and `NEWS_API_KEY` in `.env`. The `.env` file is listed in `.gitignore` and is never committed.

## Usage
```bash
python main.py                     # interactive app (1-5 articles)
python summarizer.py 3             # summarize 3 articles directly
python llm_providers.py fallback   # demonstrate fallback between providers
pytest test_summarizer.py -v       # run the tests
```

## Settings (`.env`)
`MAX_RETRIES=3`, `REQUEST_TIMEOUT=30`, `DAILY_BUDGET=5.00`, `OPENAI_MODEL`, `COHERE_MODEL`.

## Example output
The program prints in Spanish (real output from a run):
```
=== 3 de 3 noticias procesadas correctamente ===

✓ 2. India calls for action from Meta amid election protests
   Resumen (cohere): El gobierno de India exige a Meta ... que revise sus algoritmos de recomendación ...
   Sentimiento (cohere): negativo

--- Resumen de costes ---
cohere  command-r-08-2024  entrada= 277 salida=  55 coste=$0.000075
cohere  command-r-08-2024  entrada= 278 salida=   4 coste=$0.000044
...
TOTAL: $0.000376 de $5.00 de presupuesto diario
```

## Robustness
- **Retries:** at most 3, waiting 1, 2 and 4 s. Only for temporary failures (network, 408, rate-limit 429, 5xx).
- **No retry:** wrong key (401), nonexistent model (404) and exhausted balance (`insufficient_quota`).
- **Fallback:** if one provider fails completely, the other is used.
- **Isolation:** if one article fails, the others are still processed.
- **Cost protections:** daily budget checked before every call, descriptions truncated to 500 characters and duplicate articles discarded.

## Note on OpenAI
During development the OpenAI account had no credit (error 429 `insufficient_quota`), so calls were completed by Cohere as the backup. The code does not change when credit is added: OpenAI would simply become the primary provider again.

## Cost analysis
Summarization calls cost more than sentiment calls because they return more text (55 to 81 output tokens versus 3 or 4), as shown in the cost summary. Even so, the difference is small, because cost depends mainly on input tokens: every call sends the instruction plus the text of the article (title and description) or of the summary, and that is similar in both. Processing 3 articles cost $0.000376, about $0.000125 per article, so 1,000 articles would cost roughly $0.125, far below the daily budget of $5.00.

## Known limitations
- Spent budget is not persisted between runs.
- Per-token prices are hard-coded in `llm_providers.py` and should be verified.
- Calls are sequential (no async).
