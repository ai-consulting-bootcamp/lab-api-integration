# Lab summary

I built a news workflow that fetches technology articles, summarizes them with OpenAI, sends each summary to Anthropic for sentiment analysis, and reports recurring topics and estimated cost. The main challenges were handling provider differences and failures, which I addressed with environment-based configuration, isolated provider clients, and per-article fallback output. I learned how to pass structured output between APIs and how to test the workflow without making live requests; a future improvement would be stronger rate limiting and persistent cost storage.
