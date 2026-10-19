import pytest
from unittest.mock import patch
from summarizer import NewsSummarizer

@patch('summarizer.fetch_latest_news')
@patch('summarizer.ask_with_fallback')
def test_process_articles_success(mock_ask, mock_fetch):
    """Tests the pipeline using faked data to avoid real API costs."""
    
    # 1. Mock the News API returning exactly one fake article
    mock_fetch.return_value = [
        {
            "title": "New AI Model Released", 
            "source": "Tech Daily", 
            "content": "A new AI model was released today that writes unit tests automatically."
        }
    ]
    
    # 2. Mock the LLM routing: First call is the summary, second is the sentiment
    mock_ask.side_effect = [
        ("The new AI model automates unit testing.", "OpenAI"),
        ("Positive", "Cohere")
    ]
    
    # 3. Run the pipeline
    summarizer = NewsSummarizer()
    results = summarizer.process_articles(limit=1)
    
    # 4. Verify the outputs match exactly what we expect
    assert len(results) == 1
    assert results[0]["title"] == "New AI Model Released"
    assert results[0]["summary"] == "The new AI model automates unit testing."
    assert results[0]["sentiment"] == "Positive"
    assert results[0]["summary_provider"] == "OpenAI"
    assert results[0]["sentiment_provider"] == "Cohere"

@patch('summarizer.fetch_latest_news')
def test_no_articles_fetched(mock_fetch):
    """Tests that the pipeline handles empty news API responses gracefully."""
    mock_fetch.return_value = []
    
    summarizer = NewsSummarizer()
    results = summarizer.process_articles(limit=2)
    
    assert results == []