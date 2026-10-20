
from unittest.mock import patch

from llm_providers import calculate_cost
from summarizer import summarize_with_fallback


def test_cost_calculation():
    """Verify that token cost calculations are correct."""
    result = calculate_cost(1000, 500, 1.0, 2.0)
    assert result == 0.002


def test_openai_success():
    """Verify OpenAI is used when available."""
    article = {"title": "Test news"}

    with patch(
        "summarizer.summarize_article",
        return_value="Test summary"
    ):
        result = summarize_with_fallback(article)

    assert result == "Test summary"


def test_openai_fallback():
    """Verify Cohere is used when OpenAI fails."""
    article = {
        "title": "Test news",
        "description": "Test description",
        "content": "Test content"
    }

    mock_response = type("Response", (), {
        "message": type("Message", (), {
            "content": [
                type("Block", (), {
                    "type": "text",
                    "text": "Cohere fallback summary"
                })()
            ]
        })()
    })()

    with patch(
        "summarizer.summarize_article",
        side_effect=RuntimeError("OpenAI unavailable")
    ):
        with patch(
            "summarizer.cohere_client.chat",
            return_value=mock_response
        ):
            result = summarize_with_fallback(article)

    assert result == "Cohere fallback summary"
