# Multi-Provider News Summarizer

A Python command-line workflow that retrieves news with AskNews, summarizes it with OpenAI, and classifies the summary's sentiment with Cohere. If an AI provider fails, the other provider can perform that task.

This is a bootcamp lab and a working proof of the critical data path, not a production news service.

## Workflow

```text
Search query → AskNews context → OpenAI summary → Cohere sentiment → CLI output
                                     ↓ fallback       ↓ fallback
                                   Cohere            OpenAI
```

The app produces one summary for the retrieved news context, not a separate summary for every article. It reports an estimated LLM cost and the remaining local daily budget.

## Requirements

- Python 3.11 or later
- An AskNews API key with the `news` scope
- OpenAI and Cohere API keys

The original lab mentions Anthropic and NewsAPI. This implementation uses **Cohere** and **AskNews**, as specified for our class.

## Setup

Clone the repository and enter its directory:

```bash
git clone https://github.com/Armin-Seyfi/lab-api-integration.git
cd lab-api-integration
```

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

Copy `.env.example` to `.env`, then replace the placeholder API keys with your own:

```bash
cp .env.example .env
```

`.env` contains credentials and is excluded from Git. Never commit or share its values.

## Run

Start the interactive workflow:

```bash
python main.py
```

Enter a news query and an article count from 1 to 5. A request to AskNews and calls to the AI providers may consume API quota or incur charges.

For individual checkpoints:

```bash
python config.py
python news_api.py
python llm_providers.py
python summarizer.py
```

The last three commands make live API requests.

## Example result

A live run with the query `the new British Prime Minister` and three articles produced a summary and a `positive` sentiment label. The CLI reported:

```text
Cost: {'estimated_total_usd': 0.000239, 'remaining_daily_usd': 0.009522}
```

The remaining amount includes earlier runs on the same day. Generated news claims require comparison with their original sources; successful execution does not establish factual accuracy.

## Reliability and cost controls

- **Fallback:** OpenAI normally summarizes; Cohere takes over if OpenAI fails. Cohere normally classifies sentiment; OpenAI takes over if Cohere fails. If both providers fail, the app reports a workflow error.
- **Output validation:** A sentiment response is accepted only if it contains one unambiguous `positive`, `negative`, or `neutral` label. An ambiguous response activates fallback.
- **Rate limit:** A local SQLite ledger permits at most `MAX_LLM_REQUESTS_PER_MINUTE` LLM requests in a rolling 60-second window. Fallback requests also count. This local limit does not replace provider account quotas.
- **Daily budget:** A separate SQLite ledger reserves estimated maximum LLM cost before each request and settles completed streams using provider usage metadata. The budget day follows the Europe/Berlin timezone.
- **Streaming:** The app checks estimated cost as output chunks arrive. If a stream exceeds its reservation, the client closes it and discards the incomplete result. The CLI displays a result only after a complete response.
- **Cost scope:** `DAILY_BUDGET` covers estimated OpenAI and Cohere usage made by this application. It does not include AskNews, calls from other applications, taxes, or provider-specific billing adjustments. Mid-stream cancellation is a best-effort control, not a guaranteed billing cutoff.

The SQLite ledgers are local runtime files and are excluded from Git. An interrupted request may leave its reservation in place for that day because its final billed usage is unknown.

## Tests

Run the tests without making live API calls:

```bash
pytest test_summarizer.py -v
```

The tests cover provider routing and fallback, invalid input, AskNews failure handling, rate-limit persistence, budget reservation and settlement, streaming cancellation, and sentiment output validation. The latest local run passed **18 tests**.

## Project files

- `config.py` — environment configuration
- `news_api.py` — AskNews retrieval and input checks
- `llm_providers.py` — streaming OpenAI/Cohere calls, fallback, and cost estimates
- `summarizer.py` — workflow orchestration
- `rate_limit.py` — persistent local request limit
- `budget.py` — persistent daily budget reservations
- `stream_control.py` — streamed output collection and budget checks
- `main.py` — command-line interface
- `test_summarizer.py` — tests using mocks and temporary SQLite databases

## Current limitations

AskNews returns prompt-ready context as a string, so the app does not retain article-level source records in its final output. It has no automated factual verification, scheduling, shared database for multiple deployed instances, or deployment pipeline. Async processing was an optional stretch task and is not implemented.

The prices in `llm_providers.py` are configuration assumptions used for estimates. Review provider pricing and billing records before using the app for financial reporting.