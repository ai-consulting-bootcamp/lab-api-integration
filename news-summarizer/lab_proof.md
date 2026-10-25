# Lab proof

## Workflow configuration

`NewsSummarizer.run()` executes this path:

```text
NewsAPI top-headlines -> OpenAI summary -> Anthropic sentiment -> topic counts + cost output
```

Secrets are loaded from `.env`; no credentials belong in this file.

## Input payload

```json
{
  "title": "AI breakthrough",
  "description": "A new AI system was announced.",
  "url": "https://example.com/news"
}
```

## Execution trace

```text
Title: AI breakthrough
Summary: A new AI system was announced.
Sentiment: Positive
```

The trace is reproduced by `pytest test_summarizer.py -v` using mocked providers.

## Output record

```json
{
  "title": "AI breakthrough",
  "summary": "A new AI system was announced.",
  "sentiment": "Positive"
}
```
