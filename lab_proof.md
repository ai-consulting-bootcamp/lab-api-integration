# Lab Proof — Multi-Provider News Summarizer

## 1. Configuration

The application uses environment variables to manage API credentials and operational settings.

```env
OPENAI_API_KEY=[REDACTED]
COHERE_API_KEY=[REDACTED]
NEWS_API_KEY=[REDACTED]
ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

API keys are stored in the local `.env` file and excluded from version control.

## 2. Input

The application was executed using:

```bash
python main.py
```

User selections:

- News category: Technology
- Number of articles: 3
- Country: United States

NewsAPI returned three articles, which were processed by the application.

## 3. Execution Trace

```text
Fetching 3 technology news articles...

Processing article 1/3...
Completed: Cyberleek drops more NSFW Lucia videos...

Processing article 2/3...
Completed: Players on Steam so far seem delighted...

Processing article 3/3...
Completed: What Is The Most Affordable Gaming Console In 2026?
```

All three articles completed processing successfully.

## 4. Output Evidence

| Article | Sentiment | Estimated cost |
|---|---|---|
| GTA 6 leak coverage | Negative | $0.000565 |
| Modern Warfare 4 player reception | Positive | $0.000758 |
| Affordable gaming consoles | Neutral | $0.000630 |

**Total estimated API cost:** $0.001954

**Configured budget:** $5.00

The application generated summaries and sentiment analyses for all three articles.

## 5. Automated Test Evidence

Command executed:

```bash
pytest test_summarizer.py -v
```

Result:

```text
collected 13 items

13 passed in 2.94s
```

The tests verified article processing, provider fallback, temporary error retries, rate limiting, and budget enforcement.

Fallback and retry behavior was tested using mocked failures rather than actual provider outages.

## 6. Evidence and Limitations

The successful interactive run demonstrates that NewsAPI retrieval, OpenAI summarization, Cohere sentiment analysis, and cost reporting work together.

The automated tests demonstrate the expected behavior of several reliability mechanisms under simulated conditions.

The evidence does not establish production-level availability, persistent budget enforcement, or full-article accuracy.

## 7. Screenshots


- The interactive application menu and user selections.
- The generated summaries, sentiment results, and cost report.
- The terminal showing all 13 pytest tests passing.

