# News Summarizer

A Python terminal application that searches for news, summarizes the available article excerpts with OpenAI, and analyzes their sentiment with Cohere.

## What it does

1. Asks for a search topic.
2. Fetches up to `ARTICLE_COUNT` English-language articles from NewsAPI.org, sorted by relevance.
3. Combines each article's title, description, and available content.
4. Uses OpenAI `gpt-4o-mini` to generate a German summary of at most two sentences.
5. Uses Cohere `command-a-03-2025` to classify the same original excerpt as `positiv`, `negativ`, or `neutral`.
6. Displays results and total input/output tokens for each provider.

The current configuration requests **three articles**. Change `ARTICLE_COUNT` in `config.py` to `2` if you want two instead. Fewer results may be returned; articles without usable text are skipped.

NewsAPI does not supply full article bodies: its `content` field is truncated to 200 characters. Summaries and sentiment therefore describe the available excerpts, not a verified reading of the complete articles. See the [NewsAPI endpoint documentation](https://newsapi.org/docs/endpoints/everything).

## Setup

Use Python 3.11 or newer. You need API keys for NewsAPI.org, OpenAI, and Cohere, plus access to the models listed above.

From the repository root, enter the application directory:

```powershell
cd news-summarizer
```

If using the existing course environment:

```powershell
conda activate bootcamp-env
```

Alternatively, create and activate a separate environment:

```powershell
conda create -n news-summarizer python=3.11
conda activate news-summarizer
```

Install the dependencies in the active environment:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file inside `news-summarizer` with your own values:

```dotenv
NEWS_API_KEY=your_newsapi_key
OPENAI_API_KEY=your_openai_key
COHERE_API_KEY=your_cohere_key
REQUEST_TIMEOUT=30
```

All three keys are required. `REQUEST_TIMEOUT` is optional, defaults to 30 seconds, and must be a positive integer. Existing environment variables take precedence over `.env` values. The file is loaded relative to `config.py`, independent of the terminal's working directory.

Keep real keys private. `.env` is excluded by the project's `.gitignore`.

## Run

From inside `news-summarizer`:

```powershell
python main.py
```

Enter a topic such as `solar energy` or an exact phrase such as `"artificial intelligence"`. An empty topic ends the application without making requests.

From the repository root, use `python news-summarizer/main.py` instead. In the IDE, select the same Python environment and choose **Run Python File in Terminal** with `main.py` active.

Each run makes one NewsAPI request and, for each usable article, one OpenAI request followed by one Cohere request. The program currently stops if a service raises an error. Calls completed before an error may still incur charges.

## Example output

Illustrative example with `ARTICLE_COUNT = 1`; article text and token numbers are sample data, not a guaranteed response:

```text
News Summarizer - OpenAI und Cohere
Nach welchem Thema moechtest du suchen? solar energy
Artikel werden geladen und analysiert ...

1. New solar project announced
Link: https://example.com/solar-project
Zusammenfassung: Ein neues Solarprojekt soll 10.000 Haushalte mit Strom versorgen und 200 Arbeitsplätze schaffen.
Stimmung: positiv
------------------------------------------------------------

TOKENVERBRAUCH
OPENAI: Input 150 | Output 40 | Gesamt 190
COHERE: Input 160 | Output 1 | Gesamt 161
Tokenzahlen sind keine Geldkosten; diese werden noch nicht berechnet.
```

## Unit tests

From inside `news-summarizer`:

```powershell
python -m unittest test_summarizer -v
```

The six tests replace the external API functions with mocks. They check article processing, reuse of supplied articles, token addition, missing fields, empty input, and provider error propagation. They make no real API requests and consume no LLM tokens.

Dependencies and configuration are still required because the tests import the application modules, which initialize the clients. Tests validate application logic, not live credentials or model response quality.

## Cost analysis

The application reports token usage, **not dollar costs**. OpenAI counts come from `response.usage`; Cohere counts come from `response.usage.billed_units`. Input includes instructions and the article excerpt. Both providers receive the original excerpt separately, so both have input costs.

Standard text rates checked on **October 19, 2026**, in USD per one million tokens:

- OpenAI `gpt-4o-mini`: $0.15 input and $0.60 output. [Official OpenAI model pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini).
- Cohere `command-a-03-2025`: $2.50 input and $10.00 output. [Official Cohere model pricing](https://docs.cohere.com/docs/command-a).

For each provider:

```text
estimated cost = (input tokens × input rate + output tokens × output rate) / 1,000,000
```

A previously successful three-article run reported these counts:

- OpenAI: 458 input + 173 output tokens. Estimate: `(458 × 0.15 + 173 × 0.60) / 1,000,000 = $0.0001725`.
- Cohere: 465 input + 4 output tokens. Estimate: `(465 × 2.50 + 4 × 10) / 1,000,000 = $0.0012025`.
- Combined estimated LLM cost: **$0.001375 per run**, or about **$1.38 for 1,000 runs with exactly the same usage**.

These are list-price estimates, not an invoice. They exclude NewsAPI plan charges, taxes, retries, discounts, caching, and credits. Usage varies with article length and generated text. Cohere trial keys are free subject to applicable trial limits; production keys are billed. See [Cohere billing information](https://cohere.com/pricing) and your provider dashboards for actual charges. NewsAPI requests use a separate quota, not LLM tokens; consult your [NewsAPI plan](https://newsapi.org/pricing).

To reduce usage, request fewer articles, keep output concise, and use the unit tests for logic checks instead of repeatedly running live calls. Reusing saved articles avoids NewsAPI requests but still invokes both LLM providers.

## Project files

- `config.py`: loads and validates settings.
- `news_api.py`: searches NewsAPI.
- `llm_providers.py`: calls OpenAI and Cohere and returns text plus token usage.
- `summarizer.py`: coordinates processing and adds token totals.
- `main.py`: terminal input and result display.
- `test_summarizer.py`: mocked unit tests.

## Troubleshooting

- **File not found:** if already inside `news-summarizer`, run `python main.py`, without repeating the folder name.
- **Missing package:** select the correct environment and reinstall with `python -m pip install -r requirements.txt`.
- **Missing API key:** check the exact variable names in `.env`.
- **403 or model access error:** verify project permissions and model availability. Model IDs are configured in `llm_providers.py`.
- **Network, quota, or rate-limit error:** check connectivity and the relevant provider account.
