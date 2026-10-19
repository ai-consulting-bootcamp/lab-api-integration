from unittest.mock import patch
from summarizer import NewsSummarizer


def test_fetch_articles():
    """Test fetching news articles using mocked API data."""

    # Simulate NewsAPI response
    fake_articles = [
        {"title": "Article 1"},
        {"title": "Article 2"}
    ]

    # Mock external dependencies
    with patch("summarizer.NewsAPI") as mock_news_api, \
         patch("summarizer.LLMProviders"):

        mock_news_api.return_value.get_articles.return_value = fake_articles

        # Initialize summarizer
        summarizer = NewsSummarizer()

        # Fetch articles
        result = summarizer.fetch_articles(limit=2)

    # Verify results
    assert result == fake_articles

    # Verify correct API parameters
    mock_news_api.return_value.get_articles.assert_called_once_with(
        category="technology",
        limit=2
    )

def test_summarize_article():
    """Test article summarization using a mocked OpenAI response."""

    # Create fake article
    fake_article = {
        "title": "New AI Technology Released",
        "description": "A company released a new AI model.",
        "content": "The model improves AI performance."
    }

    # Mock external dependencies
    with patch("summarizer.NewsAPI"), \
         patch("summarizer.LLMProviders") as mock_llm:

        # Simulate OpenAI response
        mock_llm.return_value.ask_openai.return_value = {
            "response": "A new AI model has been released."
        }

        # Initialize summarizer
        summarizer = NewsSummarizer()

        # Generate summary
        result = summarizer.summarize_article(fake_article)

    # Verify summary
    assert result == "A new AI model has been released."

    # Verify OpenAI was called
    mock_llm.return_value.ask_openai.assert_called_once()

    # Verify article title was included in the prompt
    prompt = mock_llm.return_value.ask_openai.call_args.args[0]
    assert fake_article["title"] in prompt

def test_analyze_sentiment():
    """Test sentiment analysis using a mocked Cohere response."""

    # Create fake summary
    fake_summary = "The new AI technology improves productivity."

    # Mock external dependencies
    with patch("summarizer.NewsAPI"), \
         patch("summarizer.LLMProviders") as mock_llm:

        # Simulate Cohere response
        mock_llm.return_value.ask_cohere.return_value = {
            "response": "Positive: The summary highlights improvements."
        }

        # Initialize summarizer
        summarizer = NewsSummarizer()

        # Analyze sentiment
        result = summarizer.analyze_sentiment(fake_summary)

    # Verify sentiment result
    assert result == "Positive: The summary highlights improvements."

    # Verify Cohere was called exactly once
    mock_llm.return_value.ask_cohere.assert_called_once()

    # Verify summary was included in the prompt
    prompt = mock_llm.return_value.ask_cohere.call_args.args[0]
    assert fake_summary in prompt

def test_process_articles():
    """Test the complete news processing workflow using mocks."""

    # Create fake news articles
    fake_articles = [
        {
            "title": "AI News 1",
            "source": {"name": "Tech News"},
            "url": "https://example.com/1"
        },
        {
            "title": "AI News 2",
            "source": {"name": "AI Magazine"},
            "url": "https://example.com/2"
        }
    ]

    # Mock external dependencies
    with patch("summarizer.NewsAPI") as mock_news_api, \
         patch("summarizer.LLMProviders") as mock_llm:

        mock_news_api.return_value.get_articles.return_value = fake_articles

        # Simulate OpenAI summaries
        mock_llm.return_value.ask_openai.side_effect = [
            {"response": "Summary of article 1"},
            {"response": "Summary of article 2"}
        ]

        # Simulate Cohere sentiment analyses
        mock_llm.return_value.ask_cohere.side_effect = [
            {"response": "Positive"},
            {"response": "Neutral"}
        ]

        # Run complete workflow
        summarizer = NewsSummarizer()
        results = summarizer.process_articles(limit=2)

    # Verify number of processed articles
    assert len(results) == 2

    # Verify results
    assert results[0]["summary"] == "Summary of article 1"
    assert results[0]["sentiment"] == "Positive"

    assert results[1]["summary"] == "Summary of article 2"
    assert results[1]["sentiment"] == "Neutral"

    # Verify both providers were called twice
    assert mock_llm.return_value.ask_openai.call_count == 2
    assert mock_llm.return_value.ask_cohere.call_count == 2