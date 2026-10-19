# Multi-Provider News Summarizer

## Project Overview

This project is a Python-based news summarization application developed as part of the Ironhack AI Consulting Bootcamp.

The application fetches news articles from NewsAPI, uses OpenAI to generate short summaries, and uses Cohere to analyze the sentiment of each summary.

The goal of this project was to build an automated workflow that connects multiple APIs, processes information, handles API failures, and tracks usage costs.

## Features

- Fetch news articles using NewsAPI.
- Summarize articles using OpenAI (`gpt-4o-mini`).
- Analyze sentiment using Cohere (`command-r7b-12-2024`).
- Classify sentiment as Positive, Negative, or Neutral, with an explanation.
- Track token usage and estimated API costs for both LLM providers.
- Manage a configurable budget.
- Support automatic retries and an OpenAI-to-Cohere fallback mechanism.
- Test core functionality using mocked API responses.
- Run the application through an interactive command-line interface.

## Project Structure

```text
lab-api-integration/
├── .env.example
├── .gitignore
├── requirements.txt
├── config.py
├── news_api.py
├── llm_providers.py
├── summarizer.py
├── test_summarizer.py
├── main.py
├── README.md
└── lab_summary.md
```

### Module Responsibilities

| File | Description |
|---|---|
| `config.py` | Loads environment variables, API keys, and application settings |
| `news_api.py` | Fetches news articles from NewsAPI |
| `llm_providers.py` | Handles OpenAI and Cohere requests, retry configuration, fallback logic, and cost tracking |
| `summarizer.py` | Coordinates article retrieval, summarization, and sentiment analysis |
| `test_summarizer.py` | Contains unit tests using mocked API responses |
| `main.py` | Provides the interactive command-line application |

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd lab-api-integration
```

Replace `<repository-url>` with the actual GitHub repository URL.

### 2. Install Dependencies

Python 3.11 was used during development.

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to a new file named `.env`.

Insert your own API keys:

```dotenv
OPENAI_API_KEY=your_openai_api_key
COHERE_API_KEY=your_cohere_api_key
NEWS_API_KEY=your_news_api_key

ENVIRONMENT=development
MAX_RETRIES=3
REQUEST_TIMEOUT=30
DAILY_BUDGET=5.00
```

API keys are required from:

- OpenAI: https://platform.openai.com/
- Cohere: https://dashboard.cohere.com/
- NewsAPI: https://newsapi.org/

The `.env` file is excluded from Git to prevent accidental exposure of API credentials.

### 4. Validate Configuration

```bash
python config.py
```

This checks whether the required environment variables are available.

## Running the Application

Start the interactive application:

```bash
python main.py
```

The application prompts the user to select the number of articles