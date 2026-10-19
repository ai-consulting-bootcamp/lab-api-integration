"""Unit tests: no real API calls, everything is faked."""
import pytest
from config import get_config
from llm_providers import LLMProviders, CostTracker, BudgetExceededError
from summarizer import (NewsSummarizer, article_text, build_summary_prompt,
                        build_sentiment_prompt, clean_sentiment)

ARTICLE = {"title": "AI lab opens in Berlin", "description": "A new lab opened.",
           "content": "", "source": "Test News", "url": "https://example.com",
           "published_at": "2026-10-19"}
TITLE_ONLY = {**ARTICLE, "description": "", "content": ""}


class FakeLLM:
    """Pretends to be LLMProviders. Returns fixed answers, costs nothing."""
    def __init__(self):
        self.costs = CostTracker(daily_budget=5.0)
        self.prompts = []

    def ask_with_fallback(self, prompt, primary="openai"):
        self.prompts.append(prompt)
        if "Label:" in prompt:
            return "Positive.", "cohere"
        return "A short fake summary.", "openai"


# ---------- config ----------
def test_config_loads():
    config = get_config()
    assert config.max_retries > 0 and config.daily_budget > 0


def test_config_missing_key(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="COHERE_API_KEY"):
        get_config()


# ---------- helpers ----------
def test_article_text_uses_description():
    assert article_text(ARTICLE) == ("A new lab opened.", False)


def test_article_text_falls_back_to_title():
    assert article_text(TITLE_ONLY) == ("AI lab opens in Berlin", True)


def test_title_only_prompt_warns_model():
    assert "Do not invent" in build_summary_prompt(TITLE_ONLY)


def test_sentiment_prompt_lists_labels():
    prompt = build_sentiment_prompt("Some summary")
    assert "positive, negative, neutral" in prompt and prompt.endswith("Label:")


@pytest.mark.parametrize("raw, expected", [
    ("positive", "positive"), ("Negative.", "negative"),
    ("  NEUTRAL ", "neutral"), ("It is mixed", "unknown"), ("", "unknown")])
def test_clean_sentiment(raw, expected):
    assert clean_sentiment(raw) == expected


# ---------- costs ----------
def test_cost_calculation():
    tracker = CostTracker(daily_budget=5.0)
    cost = tracker.add("openai", input_tokens=1_000_000, output_tokens=0)
    assert cost == pytest.approx(0.15)


def test_budget_exceeded():
    tracker = CostTracker(daily_budget=0.000001)
    tracker.add("openai", input_tokens=1000, output_tokens=1000)
    with pytest.raises(BudgetExceededError):
        tracker.check_budget()


# ---------- fallback ----------
def make_llm_without_network():
    llm = LLMProviders.__new__(LLMProviders)     # skip __init__: no real clients
    llm.costs = CostTracker(daily_budget=5.0)
    return llm


def test_fallback_switches_provider():
    llm = make_llm_without_network()
    def fake_call(provider, prompt):
        if provider == "openai":
            raise RuntimeError("[openai] failed: AuthenticationError")
        return "backup answer"
    llm._call_with_retry = fake_call
    assert llm.ask_with_fallback("hi", primary="openai") == ("backup answer", "cohere")


def test_budget_error_does_not_fall_back():
    llm = make_llm_without_network()
    def fake_call(provider, prompt):
        raise BudgetExceededError("no money")
    llm._call_with_retry = fake_call
    with pytest.raises(BudgetExceededError):
        llm.ask_with_fallback("hi")


# ---------- full pipeline (with fake AI) ----------
def test_process_article_builds_record():
    record = NewsSummarizer(llm=FakeLLM()).process_article(ARTICLE)
    assert record["summary"] == "A short fake summary."
    assert record["sentiment"] == "positive"
    assert record["summary_provider"] == "openai"
    assert record["sentiment_provider"] == "cohere"


def test_summary_is_passed_to_sentiment_step():
    fake = FakeLLM()
    NewsSummarizer(llm=fake).process_article(ARTICLE)
    assert "A short fake summary." in fake.prompts[1]   # the handoff