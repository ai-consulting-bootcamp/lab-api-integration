"""Pruebas automáticas. No llaman a ninguna API real: no cuestan dinero."""
import pytest
import requests

import config
import llm_providers as llm
import news_api
import summarizer


class FakeAPIError(Exception):
    """Imita un error de un proveedor, con su código HTTP."""
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


@pytest.fixture(autouse=True)
def fast_and_safe(monkeypatch):
    """Sin esperas reales y con ajustes conocidos en todas las pruebas."""
    monkeypatch.setattr(llm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    monkeypatch.setattr(config, "NEWS_API_KEY", "clave-falsa")


def ok_result(provider_model=llm.OPENAI_MODEL):
    return {"text": "hola", "model": provider_model, "input_tokens": 100, "output_tokens": 20}


# ---------- Costes ----------
def test_cost_is_calculated_from_exact_tokens():
    tracker = llm.CostTracker(daily_budget=5)
    cost = tracker.record("openai", llm.OPENAI_MODEL, 1000, 200)
    assert cost == pytest.approx(0.00027)


def test_budget_blocks_new_calls_when_spent():
    tracker = llm.CostTracker(daily_budget=0.001)
    tracker.record("openai", llm.OPENAI_MODEL, 1_000_000, 0)
    with pytest.raises(llm.BudgetExceededError):
        tracker.check_budget()


# ---------- Reintentos y fallback ----------
def test_retries_three_times_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def flaky(prompt):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise FakeAPIError("saturado", 429)
        return ok_result()

    result = llm.call_with_retries(flaky, "x", "openai")
    assert result["text"] == "hola" and attempts["n"] == 3


def test_never_exceeds_max_retries():
    attempts = {"n": 0}

    def always_down(prompt):
        attempts["n"] += 1
        raise FakeAPIError("caído", 503)

    with pytest.raises(llm.ProviderError):
        llm.call_with_retries(always_down, "x", "openai")
    assert attempts["n"] == config.MAX_RETRIES


def test_bad_key_is_not_retried():
    attempts = {"n": 0}

    def bad_key(prompt):
        attempts["n"] += 1
        raise FakeAPIError("clave inválida", 401)

    with pytest.raises(llm.ProviderError):
        llm.call_with_retries(bad_key, "x", "openai")
    assert attempts["n"] == 1


def test_no_credit_error_is_not_retried():
    calls = {"n": 0}

    def no_credit(prompt):
        calls["n"] += 1
        raise FakeAPIError("Error code: 429 - insufficient_quota", 429)

    with pytest.raises(llm.ProviderError):
        llm.call_with_retries(no_credit, "x", "openai")
    assert calls["n"] == 1


def test_fallback_uses_secondary_when_primary_fails(monkeypatch):
    def down(prompt):
        raise FakeAPIError("caído", 503)

    monkeypatch.setitem(llm.PROVIDERS, "openai", down)
    monkeypatch.setitem(llm.PROVIDERS, "cohere", lambda prompt: ok_result(llm.COHERE_MODEL))
    result = llm.ask("x", tracker=llm.CostTracker(daily_budget=5))
    assert result["provider"] == "cohere" and result["used_fallback"] is True


def test_both_providers_failing_raises(monkeypatch):
    def down(prompt):
        raise FakeAPIError("caído", 500)

    monkeypatch.setitem(llm.PROVIDERS, "openai", down)
    monkeypatch.setitem(llm.PROVIDERS, "cohere", down)
    with pytest.raises(llm.ProviderError):
        llm.ask("x", tracker=llm.CostTracker(daily_budget=5))


# ---------- Resumidor ----------
ARTICLES = [{"title": f"Noticia {i}", "source": "s", "description": "d", "url": "u"} for i in range(1, 4)]


def test_one_failed_article_does_not_stop_the_rest(monkeypatch):
    monkeypatch.setattr(summarizer, "fetch_news", lambda *args, **kwargs: ARTICLES)

    def fake_ask(prompt, primary, secondary, tracker):
        if "Noticia 2" in prompt:
            raise llm.ProviderError("fallaron los dos")
        return {"text": "positivo" if "Clasifica" in prompt else "resumen", "provider": primary}

    monkeypatch.setattr(summarizer, "ask", fake_ask)
    results, _ = summarizer.summarize_news(3, llm.CostTracker(daily_budget=5))
    assert [r["status"] for r in results] == ["ok", "error", "ok"]


def test_unexpected_sentiment_is_marked_undefined(monkeypatch):
    monkeypatch.setattr(summarizer, "ask", lambda *a, **k: {"text": "ni idea qué decir", "provider": "cohere"})
    sentiment, _ = summarizer.analyze_sentiment("texto", llm.CostTracker(daily_budget=5))
    assert sentiment == "indefinido"


def test_duplicate_articles_are_removed():
    dup = [{"title": "Misma noticia", "description": "a"}, {"title": " misma NOTICIA ", "description": "b"},
           {"title": "Otra", "description": "c"}]
    assert [a["title"] for a in summarizer.remove_duplicates(dup)] == ["Misma noticia", "Otra"]


def test_huge_description_is_truncated_before_sending(monkeypatch):
    sent = {}

    def fake_ask(prompt, primary, secondary, tracker):
        sent["prompt"] = prompt
        return {"text": "resumen", "provider": primary}

    monkeypatch.setattr(summarizer, "ask", fake_ask)
    article = {"title": "T", "description": "x" * 10_000}
    summarizer.summarize_article(article, llm.CostTracker(daily_budget=5))
    assert len(sent["prompt"]) < summarizer.MAX_DESCRIPTION_CHARS + 300


# ---------- Noticias ----------
class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload

    def json(self):
        return self._payload


def test_news_removes_deleted_articles(monkeypatch):
    payload = {"status": "ok", "articles": [
        {"title": "Buena", "source": {"name": "BBC"}, "description": None, "url": "u"},
        {"title": "[Removed]", "source": {"name": "x"}},
    ]}
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(200, payload))
    articles = news_api.fetch_news("technology")
    assert len(articles) == 1 and articles[0]["title"] == "Buena"


def test_news_rejected_key_raises_clear_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(401, {}))
    with pytest.raises(news_api.NewsAPIError):
        news_api.fetch_news("technology")
