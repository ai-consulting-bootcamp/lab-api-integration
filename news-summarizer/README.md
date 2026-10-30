# Multi-Provider News Summarizer

This small Python app fetches technology news, asks OpenAI to summarize each article, and asks Anthropic Claude to label the article's mood as positive, negative, or neutral. If Anthropic is unavailable, the app uses OpenAI for the mood label instead.

## What it does

1. Fetches up to three technology headlines from News API.
2. Summarizes each article with OpenAI.
3. Labels its mood with Anthropic, with OpenAI as a fallback.
4. Prints the title, source, summary, mood, provider, and token counts.

## Set up

Use Python 3.10 or newer. From this folder, create and activate a virtual environment, then install the packages:

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS or Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your own API keys to `.env`: OpenAI, Anthropic, and News API. Keep this file private; never commit real keys to GitHub.

## Run it

Run these commands from this folder:

```bash
python config.py
python main.py
pytest test_summarizer.py -v
```

The tests use fake news and AI responses, so they do not need live API calls. The main app uses live API keys.

## Example output

```text
Title: Example technology news
Source: Example News
Summary: A company launched a new product.
Sentiment: Positive
Sentiment provider: Anthropic
URL: https://example.com/news
```

Your actual headlines and AI answers will differ.

## Cost and limits

The app prints the number of OpenAI tokens used for summaries. It does not calculate the dollar cost of API calls. The total cost depends on the current prices and usage at each provider. News API and AI services also need working network access and valid keys. Articles without text are skipped.

## Files

- `news_api.py`: fetches headlines.
- `llm_providers.py`: calls OpenAI and Anthropic and handles fallback.
- `summarizer.py`: connects the steps.
- `main.py`: runs the app.
- `test_summarizer.py`: checks the workflow without live API calls.
- `config.py`: checks that the required keys are set.
- `.env.example`: safe template for local settings.
