llm_providers.py
Budget errors never trigger fallback. If you’re out of money, switching providers would just keep spending.
The SDKs’ built-in retries are off (max_retries=0), so a failure isn’t retried twice by two separate layers.
ProviderWithFallback returns which provider answered. That goes into your execution trace as evidence that fallback actually ran.
The prices are hardcoded. Check the OpenAI and Cohere pricing pages before writing your cost analysis.

SUMMARIZER.py
Sentiment output that doesn’t follow the format is labeled unknown, not guessed. Brittle LLM output gets caught visibly.
A failed article is skipped, but a budget error stops everything.
Each record logs summary_provider and sentiment_provider. That’s your evidence of which “brain” did the work.