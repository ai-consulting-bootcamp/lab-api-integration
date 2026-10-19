# Lab Proof – Multi-Provider News Summarizer

**Workflow (input → transform → output):**
News API (top headlines) → OpenAI `gpt-4o-mini` (2-sentence summary) → Cohere `command-r7b-12-2024` (sentiment of the summary) → JSON record + cost report.

**Reliability features:** fallback between providers · retries with exponential backoff (1 s, 2 s, 4 s), skipped for authentication errors · 1 s rate limit between calls · daily budget limit · title-only warning · check for numbers in the summary that are not in the source.

---

## 1. Configuration

Settings are read from `.env` by `config.py` (`get_config()`); missing keys stop the app with a clear message. Template (`.env.example`):

```
OPENAI_API_KEY=<your key>
COHERE_API_KEY=<your key>
NEWS_API_KEY=<your key>
ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

## 2. Input payload (one raw article as returned by News API)

```json
{
  "source": {
    "id": "google-news",
    "name": "Google News"
  },
  "author": "The Washington Post",
  "title": "Column | The surprising way walking can benefit your brain - The Washington Post",
  "description": null,
  "url": "https://news.google.com/rss/articles/CBMikwFBVV95cUxPVmdMd0s0NXZqcTlqVHhHV1JpZGxEMVk4TVJHb2pHZEdlUEdFdWdTcENKc1kxT1hsWVdGWGltVTM2Qi1UXzZXbEdIUFRaWmpoNzBJelFCVFo1clpObHY1ZGE3MHVITzE3ZEZPdmMwQTJYZVNMZXlCcHlpV2I5SlpOZkQxbVpPcHJuNnlNRjc4aThMVDA?oc=5",
  "urlToImage": null,
  "publishedAt": "2026-10-18T10:32:49Z",
  "content": null
}
```

## 3. Execution trace

**Normal run** – `python main.py`, category `science`, 4 requested (3 usable articles returned):

```
[1/3] Column | The surprising way walking can benefit your brain - The Washi
   ✅ summary by openai, sentiment by cohere: positive
[2/3] 'It was jaw-dropping': The shocking lessons from an infamous experimen
   ✅ summary by openai, sentiment by cohere: negative
[3/3] Earth's Core Is Leaking All Sorts of Materials That Have Been Trapped
   ✅ summary by openai, sentiment by cohere: positive

✅ Processed 3/3 articles
💰 Total calls: 6 | Total cost: $0.000133
  openai: 3 calls | input 292 tokens | output 132 tokens | $0.000123
  cohere: 3 calls | input 249 tokens | output 3 tokens | $0.000010
💾 Saved to output_science_20261019_170045.json
```

**Fallback run** – OpenAI key broken on purpose:

```
[2/2] "I Regretted It After Two Weeks": Homeowners Are Revealing The Popular
   🔁 FALLBACK: openai unavailable ([openai] failed: AuthenticationError). Switching to cohere.
   ✅ summary by cohere, sentiment by cohere: negative

💰 Total calls: 4 | Total cost: $0.000027
  cohere: 4 calls | input 325 tokens | output 98 tokens | $0.000027
```

The run completed without losing any article. Retries are skipped for authentication errors, because a wrong key cannot succeed on a later attempt (before this fix, each article waited 1 + 2 + 4 = 7 s for nothing).

Screenshots: `screenshots/main_run.png`, `screenshots/fallback.png`, `screenshots/pytest.png`

## 4. Output record (from `output_science_20261019_170045.json`)

```json
[
  {
    "title": "Column | The surprising way walking can benefit your brain - The Washington Post",
    "source": "Google News",
    "url": "https://news.google.com/rss/articles/CBMikwFBVV95cUxPVmdMd0s0NXZqcTlqVHhHV1JpZGxEMVk4TVJHb2pHZEdlUEdFdWdTcENKc1kxT1hsWVdGWGltVTM2Qi1UXzZXbEdIUFRaWmpoNzBJelFCVFo1clpObHY1ZGE3MHVITzE3ZEZPdmMwQTJYZVNMZXlCcHlpV2I5SlpOZkQxbVpPcHJuNnlNRjc4aThMVDA?oc=5",
    "summary": "The article discusses the unexpected benefits of walking for brain health. It highlights how walking can positively impact cognitive function.",
    "sentiment": "positive",
    "summary_provider": "openai",
    "sentiment_provider": "cohere",
    "title_only": true,
    "unsupported_numbers": []
  },
  {
    "title": "'It was jaw-dropping': The shocking lessons from an infamous experiment in obedience - BBC",
    "source": "BBC News",
    "url": "https://www.bbc.com/future/article/20261016-the-shocking-truths-about-an-infamous-experiment-in-obedience",
    "summary": "A recent analysis of obedience experiments reveals that a vast majority of participants are willing to follow authority figures, with only 2.6% of nearly 800 volunteers refusing to administer shocks to others. This finding highlights the unsettling extent to which individuals comply with directives, even when they conflict with their moral beliefs.",
    "sentiment": "negative",
    "summary_provider": "openai",
    "sentiment_provider": "cohere",
    "title_only": false,
    "unsupported_numbers": []
  },
  {
    "title": "Earth's Core Is Leaking All Sorts of Materials That Have Been Trapped Since Our Planet's Birth - ScienceAlert",
    "source": "ScienceAlert",
    "url": "https://www.sciencealert.com/earths-core-is-leaking-all-sorts-of-materials-that-have-been-trapped-since-our-planets-birth",
    "summary": "Scientists have discovered that Earth's core is leaking various materials that have been trapped since the planet's formation, providing insights into its early conditions. This finding sheds light on the planet's geological history and the processes that shaped its development over billions of years.",
    "sentiment": "positive",
    "summary_provider": "openai",
    "sentiment_provider": "cohere",
    "title_only": false,
    "unsupported_numbers": []
  }
]
```

## 5. Tests

`pytest test_summarizer.py -v` → **17 passed in 0.29 s**. All tests use a fake LLM (no network, no cost). They cover: config validation, missing-key error, title-only fallback, strict sentiment prompt, sentiment cleaning (5 cases), cost calculation, budget stop, provider fallback, no fallback on budget error, the full record, and the summary → sentiment handoff.

## 6. First failure mode I would monitor

**Silent unfaithful summaries.** The pipeline always reports success, but a summary can contain facts that are not in the source:

- One article said "2.6% of ~800 volunteers refused"; the first summary stated "97.4% complied" as if the article said it (the model calculated 100 − 2.6).
- When Cohere took over through fallback, it twice invented that a title-only article "invites readers to share photos".

Fixes added: the summary prompt now says "Use ONLY facts stated in the text", and code flags any number in a summary that does not appear in the source. In production I would track per day: the share of title-only articles, fallback runs, and flagged summaries.