import summarizer


def test_process_articles_returns_summary_and_sentiment(monkeypatch):
    """Check that an article is summarized and analyzed."""
    fake_article = {
        "title": "Example technology news",
        "description": "A company launched a new product.",
        "content": "",
        "source": {"name": "Example News"},
        "url": "https://example.com/news",
    }

    monkeypatch.setattr(
        summarizer,
        "fetch_tech_news",
        lambda: [fake_article],
    )
    monkeypatch.setattr(
        summarizer,
        "summarize_with_openai",
        lambda text: {
            "text": "The company launched a product.",
            "input_tokens": 10,
            "output_tokens": 6,
        },
    )
    monkeypatch.setattr(
        summarizer,
        "analyze_sentiment_with_fallback",
        lambda text: {
            "provider": "Anthropic",
            "sentiment": "Positive",
        },
    )

    results = summarizer.process_articles(limit=1)

    assert len(results) == 1
    assert results[0]["summary"] == "The company launched a product."
    assert results[0]["sentiment"] == "Positive"
    assert results[0]["sentiment_provider"] == "Anthropic"


def test_process_articles_skips_article_without_text(monkeypatch):
    """Check that an article without text is skipped."""
    fake_article = {
        "title": "Article with no text",
        "description": "",
        "content": "",
        "source": {"name": "Example News"},
        "url": "https://example.com/news",
    }

    monkeypatch.setattr(
        summarizer,
        "fetch_tech_news",
        lambda: [fake_article],
    )

    results = summarizer.process_articles(limit=1)

    assert results == []
