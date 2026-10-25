# Lab proof: Two Brains, Zero Single Point of Failure

## Current workflow

News API provides the article. OpenAI writes the summary. Anthropic labels the sentiment. If Anthropic fails, OpenAI is used for sentiment instead.

## Previous execution evidence

The trace below was captured before the provider was changed from Cohere to Anthropic. It documents the earlier version and does not verify the updated Anthropic code.

Command: `python main.py`

The earlier run fetched technology news, summarized articles with OpenAI, and labeled sentiment with Cohere.

Earlier test result: `pytest test_summarizer.py -v` — 2 tests passed before the provider update.

Earlier output example:

- Title: Dell releases a new 16-inch laptop with an OLED display
- Sentiment provider: Cohere

## Verify the updated version

After adding valid keys to a private `.env` file and installing the packages, run `python main.py` and `pytest test_summarizer.py -v` from the `news-summarizer` folder. Replace the earlier evidence above with the new terminal trace and output record. Do not commit the real API keys.

## Limitation

The app skips articles without text. The old trace does not show the Anthropic run; a fresh run is needed to capture that evidence.
