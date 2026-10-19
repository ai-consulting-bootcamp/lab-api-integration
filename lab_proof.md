# Lab Proof — Multi-Provider News Summarizer

## 1. Workflow configuration

The workflow is implemented in the source files in this repository:

```text
CLI input
  → AskNews search (`news_api.py`)
  → OpenAI streamed summary (`llm_providers.py`)
  → Cohere streamed sentiment (`llm_providers.py`)
  → CLI output (`main.py`)
```

OpenAI and Cohere can take over each other's task when a provider fails. `summarizer.py` coordinates the stages. `rate_limit.py`, `budget.py`, and `stream_control.py` enforce local request and estimated cost controls.

The `.env.example` file lists required settings without credentials. The live run used `DAILY_BUDGET=0.01` USD and `MAX_LLM_REQUESTS_PER_MINUTE=10`. The real `.env` and local SQLite ledgers are excluded from Git.

## 2. Input payload

The user entered this logical workflow input in the CLI:

```json
{
  "query": "the new British Prime Minister",
  "articles": 3
}
```

AskNews returned prompt-ready news context. The application passes that context as a string to OpenAI; it does not currently persist the complete AskNews response as an artifact.

## 3. Execution trace

In the observed successful run on 19 October 2026:

| Stage | Observed evidence |
|---|---|
| AskNews search | `GET /v1/news/search` → HTTP `200 OK` |
| OpenAI summarization | `POST /v1/chat/completions` → HTTP `200 OK` |
| Cohere sentiment | `POST /v2/chat` → HTTP `200 OK` |
| Destination | The CLI displayed a summary, sentiment, estimated cost, and remaining daily budget |

The complete local test command was:

```bash
pytest test_summarizer.py -v
```

Result: **18 passed, 1 warning**. The warning originates from deprecated Pydantic configuration inside the installed AskNews SDK. The tests use mocks and temporary SQLite databases; they do not make live API calls.

Tests covered normal routing, both fallback directions, failure of both providers, invalid input, AskNews failure propagation, local rate limiting, persistent budget reservations, stream cancellation, and sentiment format validation.

## 4. Output record

The CLI produced this record in the successful run:

```json
{
  "query": "the new British Prime Minister",
  "summary": "On October 19, 2026, British Prime Minister Andy Burnham launched a campaign called 'Share the Journey, Not the Noise' to combat loud music and videos on public transport. This initiative allows bus operators to impose fines of up to £100 (approximately 110 Swissfrancs) for disruptive behavior, with train fines reaching up to £1,000. The campaign aimsto enhance the commuting experience, backed by public support, though it has faced criticism from some unions for being inadequate.",
  "sentiment": "positive",
  "cost": {
    "estimated_total_usd": 0.000239,
    "remaining_daily_usd": 0.009522
  }
}
```

The summary above is the **observed model output**, preserved verbatim as execution evidence. It is not presented as a fact-checked news report. For example, a comparison with the [UK government announcement](https://www.gov.uk/government/news/share-the-journey-not-the-noise-government-launches-measures-to-prevent-noise-and-antisocial-behaviour-on-transport) shows that the campaign wording in the generated summary is imprecise. The source also does not substantiate every added detail in the summary.

## 5. Mapping and operational risk

The CLI query maps to AskNews search; the returned context maps to the OpenAI summarization input; the resulting summary maps to the Cohere sentiment input. The final CLI record combines that summary, the normalized sentiment label, and locally estimated costs.

The first failure mode I would monitor in a daily workflow is **apparently successful but factually unreliable summaries**. HTTP `200` responses and passing structural tests show that data moved through the system; they do not establish whether each generated claim is supported by a source. I would also monitor provider failures, fallback activation, rate-limit rejection, exhausted budget, and streams ending without usage metadata.

The daily cost ceiling is a best-effort local estimate for LLM calls made by this application. It excludes AskNews and cannot guarantee the provider's final bill during a cancelled stream.