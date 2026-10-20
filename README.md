# Multi-Provider News Summarizer

This lab turns `NewsAPI -> OpenAI summary -> Cohere sentiment` into a small, testable workflow.
Per the instructor correction, **Cohere replaces Anthropic everywhere in this application**.

## What the app does

- Fetches technology news from NewsAPI.
- Summarizes each article with OpenAI.
- Classifies the summary tone with Cohere.
- Falls back in both directions if a provider fails.
- Tracks request cost, rate limits, and a local daily budget.

## Repository links

- [Instructions](./instructions.md)
- [Rubric](./rubric.md)
- [Proof entry point](./lab_proof.md)
- [Lab summary](./lab_summary.md)
- [Pytest output](./screenshots/pytest-results-public.txt)
- [Manual run screenshot](./screenshots/main-run-public.png)

## Setup

Use the existing Python/conda environment already configured for this repo.
From the repository root:

```powershell
python -m pip install -r requirements.txt
```

Do not commit `.env` or any secret-bearing files.
The template below shows the expected variables from `.env.example`:

```env
OPENAI_API_KEY=
COHERE_API_KEY=
NEWS_API_KEY=
ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

## Run commands

Interactive run:

```powershell
python ./main.py
```

Reproducible non-interactive run:

```powershell
python ./main.py --category technology --count 3
```

Tests:

```powershell
python -m pytest -v
```

You can also run the checkpoint modules directly:

```powershell
python ./config.py
python ./news_api.py
python ./llm_providers.py
python ./summarizer.py
```

## Costing and budget

The app reports **estimated** cost, not actual provider billing.
Pricing was checked in code on **2026-10-20** using official provider pages:

- OpenAI: GPT-4o mini pricing/model pages.
- Cohere: Command R7B pricing/model pages.

The real manual run evidence shows:

- `run_cost_usd=0.000171`
- `daily_spend_usd=0.000320`

In the public copies, only personal local paths are hidden; the execution results are preserved.

The run total is the sum of the three article totals in the evidence, using the unrounded stage costs recorded by the providers.
The daily spend is the local ledger value after the run and may include earlier local usage from the same day.
This budget file is local to the repository and does not cover other processes or other applications using the same keys.

## Operational notes

- Rate limiting is enforced per provider.
- Retries are limited and use backoff with jitter.
- Fallback is allowed in both directions, but budget exhaustion stops the current request and does not trigger fallback.
- NewsAPI articles may be title-only, and `content` can be truncated, so summaries must not treat it as a full article text.
- The selection step requests a small buffer of candidates, then chooses unique articles without duplicating URLs.

## Real run snapshot

The manual run stored in `evidence/20261020T013150+0200_13fcdf80_inputs.json`, `evidence/20261020T013150+0200_13fcdf80_outputs.json`, and `evidence/20261020T013150+0200_13fcdf80_trace.txt` completed with `success_count=3` and `error_count=0`.
It used OpenAI for summaries and Cohere for sentiment, with no fallback needed.

A representative article from that run:

```json
{
  "source": {
    "id": null,
    "name": "Techpowerup.com"
  },
  "author": null,
  "title": "New Tools Let Users Edit and Load Modified VBIOS on GeForce RTX GPUs Without Flashing - TechPowerUp",
  "description": "A developer who goes by Panchovix has released three tools that let NVIDIA GeForce RTX 50, RTX 40, and RTX 30-series owners run a modified VBIOS without writing anything to the card's flash chip. The first is a VBIOS editor for Windows and Linux that can chan…",
  "url": "https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing",
  "urlToImage": "https://www.techpowerup.com/img/SB1pKTE8BfCEeWMc.jpg",
  "publishedAt": "2026-10-18T18:35:00Z",
  "content": "A developer who goes by Panchovix has released three tools that let NVIDIA GeForce RTX 50, RTX 40, and RTX 30-series owners run a modified VBIOS without writing anything to the card's flash chip. The… [+2074 chars]"
}
```

```json
{
  "article_index": 2,
  "article_id": "https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing",
  "title": "New Tools Let Users Edit and Load Modified VBIOS on GeForce RTX GPUs Without Flashing - TechPowerUp",
  "source": "Techpowerup.com",
  "url": "https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing",
  "published_at": "2026-10-18T18:35:00Z",
  "raw": {
    "source": {
      "id": null,
      "name": "Techpowerup.com"
    },
    "author": null,
    "title": "New Tools Let Users Edit and Load Modified VBIOS on GeForce RTX GPUs Without Flashing - TechPowerUp",
    "description": "A developer who goes by Panchovix has released three tools that let NVIDIA GeForce RTX 50, RTX 40, and RTX 30-series owners run a modified VBIOS without writing anything to the card's flash chip. The first is a VBIOS editor for Windows and Linux that can chan…",
    "url": "https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing",
    "urlToImage": "https://www.techpowerup.com/img/SB1pKTE8BfCEeWMc.jpg",
    "publishedAt": "2026-10-18T18:35:00Z",
    "content": "A developer who goes by Panchovix has released three tools that let NVIDIA GeForce RTX 50, RTX 40, and RTX 30-series owners run a modified VBIOS without writing anything to the card's flash chip. The… [+2074 chars]"
  },
  "limitations": [
    "NewsAPI content may be truncated and is not a full article text."
  ],
  "status": "ok",
  "summary": "A developer named Panchovix has introduced three tools that allow users of NVIDIA GeForce RTX 30, 40, and 50 series GPUs to run modified VBIOS without needing to alter the card's flash chip. One of the tools is a VBIOS editor compatible with both Windows and Linux.",
  "sentiment": "positive",
  "summary_stage": {
    "text": "A developer named Panchovix has introduced three tools that allow users of NVIDIA GeForce RTX 30, 40, and 50 series GPUs to run modified VBIOS without needing to alter the card's flash chip. One of the tools is a VBIOS editor compatible with both Windows and Linux.",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "usage": {
      "input_tokens": 215,
      "output_tokens": 63
    },
    "estimated_cost_usd": "0.000070",
    "attempt_cost_usd": "0.000070",
    "attempts": 1
  },
  "sentiment_stage": {
    "text": "positive",
    "provider": "cohere",
    "model": "command-r7b-12-2024",
    "usage": {
      "input_tokens": 106,
      "output_tokens": 1
    },
    "estimated_cost_usd": "0.000004",
    "attempt_cost_usd": "0.000004",
    "attempts": 1
  },
  "usage": {
    "summary": {
      "input_tokens": 215,
      "output_tokens": 63
    },
    "sentiment": {
      "input_tokens": 106,
      "output_tokens": 1
    }
  },
  "cost_usd": "0.000074",
  "factual_providers": {
    "summary": {
      "provider": "openai",
      "model": "gpt-4o-mini"
    },
    "sentiment": {
      "provider": "cohere",
      "model": "command-r7b-12-2024"
    }
  }
}
```

## Evidence and deliverables

- Full input payloads: [`evidence/20261020T013150+0200_13fcdf80_inputs.json`](./evidence/20261020T013150+0200_13fcdf80_inputs.json)
- Full output records: [`evidence/20261020T013150+0200_13fcdf80_outputs.json`](./evidence/20261020T013150+0200_13fcdf80_outputs.json)
- Execution trace: [`evidence/20261020T013150+0200_13fcdf80_trace.txt`](./evidence/20261020T013150+0200_13fcdf80_trace.txt)
- Offline fallback trace: [`evidence/simulated_offline_fallback_20261020_b67c973f_trace.txt`](./evidence/simulated_offline_fallback_20261020_b67c973f_trace.txt)
- Screenshot: [`screenshots/main-run-public.png`](./screenshots/main-run-public.png)
- Test log: [`screenshots/pytest-results-public.txt`](./screenshots/pytest-results-public.txt)

## Verification summary

- The real run completed without fallback.
- Both fallback directions were verified offline with stub clients and a temporary budget.
- The key fields line up across input, output, and trace: `title`, `source`, `url`, `published_at`, `raw`, `summary`, `sentiment`, and the provider/model metadata.
- The first operational issue to monitor in daily use is whether NewsAPI returns enough unique valid articles for the requested count.
