"""Unit tests: all external API functions are replaced with mocks."""

import unittest
from unittest.mock import call, patch

from summarizer import summarize_articles


class TestSummarizer(unittest.TestCase):
    def setUp(self):
        # Patch where summarizer uses the functions, not their original modules.
        fetch_patch = patch("summarizer.fetch_articles")
        summary_patch = patch("summarizer.summarize_text")
        sentiment_patch = patch("summarizer.analyze_sentiment")
        self.fetch = fetch_patch.start()
        self.addCleanup(fetch_patch.stop)
        self.summarize = summary_patch.start()
        self.addCleanup(summary_patch.stop)
        self.sentiment = sentiment_patch.start()
        self.addCleanup(sentiment_patch.stop)

        self.summarize.return_value = {
            "text": "Short summary", "input_tokens": 10, "output_tokens": 4,
        }
        self.sentiment.return_value = {
            "text": "neutral", "input_tokens": 8, "output_tokens": 1,
        }
        self.article = {
            "title": "Solar energy", "description": "New project",
            "content": "More details", "url": "https://example.com/news",
        }

    def test_fetches_topic_and_returns_article_results(self):
        self.fetch.return_value = [self.article]

        result = summarize_articles("solar")

        self.fetch.assert_called_once_with("solar")
        expected_text = "Solar energy\n\nNew project\n\nMore details"
        self.summarize.assert_called_once_with(expected_text)
        self.sentiment.assert_called_once_with(expected_text)
        self.assertEqual(len(result["articles"]), 1)
        article = result["articles"][0]
        self.assertEqual(article["title"], "Solar energy")
        self.assertEqual(article["url"], self.article["url"])
        self.assertEqual(article["summary"], "Short summary")
        self.assertEqual(article["sentiment"], "neutral")
        self.assertEqual(article["usage"]["openai"]["input_tokens"], 10)

    def test_saved_articles_skip_news_api(self):
        result = summarize_articles("solar", articles=[self.article])

        self.fetch.assert_not_called()
        self.assertEqual(len(result["articles"]), 1)

    def test_adds_token_usage_across_articles(self):
        self.summarize.side_effect = [
            {"text": "First", "input_tokens": 10, "output_tokens": 4},
            {"text": "Second", "input_tokens": 20, "output_tokens": 6},
        ]
        self.sentiment.side_effect = [
            {"text": "neutral", "input_tokens": 8, "output_tokens": 1},
            {"text": "positiv", "input_tokens": 12, "output_tokens": 2},
        ]

        result = summarize_articles("solar", articles=[self.article, {"title": "Wind"}])

        self.assertEqual(result["usage"], {
            "openai": {"input_tokens": 30, "output_tokens": 10},
            "cohere": {"input_tokens": 20, "output_tokens": 3},
        })
        self.assertEqual([a["summary"] for a in result["articles"]], ["First", "Second"])
        self.assertEqual(self.sentiment.call_args_list, [
            call("Solar energy\n\nNew project\n\nMore details"), call("Wind"),
        ])

    def test_missing_fields_and_blank_articles(self):
        articles = [{}, {"title": "  ", "content": None},
                    {"title": "Solar", "description": None}]

        result = summarize_articles("solar", articles=articles)

        self.summarize.assert_called_once_with("Solar")
        self.sentiment.assert_called_once_with("Solar")
        self.assertEqual(len(result["articles"]), 1)
        self.assertIsNone(result["articles"][0]["url"])

    def test_empty_list_has_zero_usage_and_no_api_calls(self):
        result = summarize_articles("solar", articles=[])

        self.fetch.assert_not_called()
        self.summarize.assert_not_called()
        self.sentiment.assert_not_called()
        self.assertEqual(result, {
            "articles": [],
            "usage": {
                "openai": {"input_tokens": 0, "output_tokens": 0},
                "cohere": {"input_tokens": 0, "output_tokens": 0},
            },
        })

    def test_provider_error_is_propagated(self):
        self.summarize.side_effect = RuntimeError("Provider unavailable")

        with self.assertRaisesRegex(RuntimeError, "Provider unavailable"):
            summarize_articles("solar", articles=[self.article])

        self.sentiment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
