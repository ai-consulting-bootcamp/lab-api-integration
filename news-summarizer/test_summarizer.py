
from unittest.mock import patch
from summarizer import NewsSummarizer


@patch("summarizer.LLMProviders")
@patch("summarizer.fetch_articles")
def test_processes_articles(mock_fetch, mock_providers):
    mock_fetch.return_value = [
        {
            "title": "AI breakthrough",
            "description": "A new AI system was announced.",
            "url": "https://example.com/news",
        }
    ]

    provider = mock_providers.return_value
    provider.total_cost = 0.000029
    provider.summarize.return_value = "A new AI system was announced."
    provider.analyze_sentiment.return_value = "Positive"

    summarizer = NewsSummarizer()
    summarizer.run()

    mock_fetch.assert_called_once_with(limit=10)
    provider.summarize.assert_called_once()
    provider.analyze_sentiment.assert_called_once()


@patch("summarizer.LLMProviders")
@patch("summarizer.fetch_articles")
def test_handles_empty_news(mock_fetch, mock_providers):
    mock_fetch.return_value = []

    summarizer = NewsSummarizer()
    summarizer.run()

    mock_providers.return_value.summarize.assert_not_called()
    mock_providers.return_value.analyze_sentiment.assert_not_called()
