# Project Rules

- Build the Multi-Provider News Summarizer in this repository root only.
- Use Cohere instead of Anthropic throughout the application.
- Implement one module at a time and keep changes small and reviewable.
- Expose a single `get_config()` interface with lowercase attributes.
- Do not perform network calls during import time.
- Keep tests offline and independent from real API credentials.
- Never print, log, or commit secrets, key fragments, hashes, or derived secret values.
- Do not invent evidence, screenshots, or execution results.
- Before implementing any API client, verify SDKs, model names, and pricing against official documentation.
