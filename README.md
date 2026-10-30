# Two Brains, Zero Single Point of Failure

**Track:** Module 2 — API Integration  
**When:** Week 3, Day 2  
**Status:** Required

# Multi-Provider News Summarizer

This project fetches technology news articles, summarizes them with OpenAI, and analyzes their sentiment with Cohere. If Cohere fails, the program uses OpenAI for sentiment analysis.

## Project files

- `news_api.py` fetches articles from News API.
- `llm_providers.py` connects to OpenAI and Cohere and includes fallback logic.
- `summarizer.py` connects news fetching, summarization, and sentiment analysis.
- `main.py` runs the workflow and displays the results.
- `test_summarizer.py` tests the workflow without making real API calls.
- `config.py` checks that the required API keys are available.

## Setup

1. Create and activate the `bootcamp-env` environment.
2. From the repository folder, enter the project folder:

   ```powershell
   cd news-summarizer
