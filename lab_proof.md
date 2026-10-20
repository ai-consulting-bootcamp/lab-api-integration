# Lab Proof

This page is the reviewer entry point for one successful real run.
Use it together with the linked evidence files and the screenshot.

## Configuration

- `.env.example`: [template](./.env.example)
- Safe runtime settings from the real run:
  - `ENVIRONMENT=development`
  - `MAX_RETRIES=3`
  - `REQUEST_TIMEOUT=30`
  - `DAILY_BUDGET=5.00`
- No API keys are shown here.

## Real run

- `run_id`: `13fcdf80`
- `time`: `2026-10-20T01:31:50+02:00`
- `command`: `python main.py --category technology --count 3`
- `result`: `success_count=3`, `error_count=0`, `run_cost_usd=0.000171`, `daily_spend_usd=0.000320`
- `fallback`: not used in this real run
- Public copies hide only personal local paths; execution results are preserved.

## Input payload

This article from the real `inputs.json` has `description` and `content`, so it is the best proof that the pipeline preserves source data and produces derived fields from the same payload.

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

## Execution trace

The trace below is the same real run and shows the stages, providers, and the selection report.

```text
run_id=13fcdf80 started_at=2026-10-20T01:31:50+02:00
request category=technology count=3
news_selection requested=5 received=4 discarded=0 selected=3 not_selected_due_to_limit=1 discard_reasons={}
article_id=https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing stage=summary provider=openai model=gpt-4o-mini attempts=1 usage=input=215 output=63 cost_usd=0.000070
article_id=https://www.techpowerup.com/353849/new-tools-let-users-edit-and-load-modified-vbios-on-geforce-rtx-gpus-without-flashing stage=sentiment provider=cohere model=command-r7b-12-2024 attempts=1 usage=input=106 output=1 cost_usd=0.000004 label=positive
```

## Output record

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

## Evidence links

- Full inputs: [`evidence/20261020T013150+0200_13fcdf80_inputs.json`](./evidence/20261020T013150+0200_13fcdf80_inputs.json)
- Full outputs: [`evidence/20261020T013150+0200_13fcdf80_outputs.json`](./evidence/20261020T013150+0200_13fcdf80_outputs.json)
- Full trace: [`evidence/20261020T013150+0200_13fcdf80_trace.txt`](./evidence/20261020T013150+0200_13fcdf80_trace.txt)
- Offline fallback trace: [`evidence/simulated_offline_fallback_20261020_b67c973f_trace.txt`](./evidence/simulated_offline_fallback_20261020_b67c973f_trace.txt)
- Screenshot: [`screenshots/main-run-public.png`](./screenshots/main-run-public.png)
- Test output: [`screenshots/pytest-results-public.txt`](./screenshots/pytest-results-public.txt)

## Matching fields

- `title`, `source`, `url`, and `published_at` are copied from the article payload.
- `raw` preserves the original article payload unchanged.
- `summary` is derived from the article text available in the payload.
- `sentiment` is derived from the summary only.
- `summary_stage` and `sentiment_stage` record the provider, model, usage, and estimated cost.

## Operational note

The first daily risk to watch is NewsAPI returning too few unique valid articles for the requested count; the pipeline must not duplicate items or invent replacements.

## Fallback note

The real run did not need fallback.
Both fallback directions were verified separately in offline mode with stub clients and a temporary budget.
