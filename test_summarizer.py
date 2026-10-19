from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from requests.exceptions import Timeout

from config import Config, ConfigError, get_config
from llm_providers import (
    BudgetExceededError,
    BudgetLedger,
    CohereAdapter,
    LLMProviderError,
    LLMResult,
    LLMService,
    OpenAIAdapter,
    PricingSpec,
)
from news_api import NewsArticle, NewsAPIError, NewsFetchDiagnostics, fetch_top_headlines
from summarizer import NewsSummarizer


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch):
    """Prevent accidental live network access during tests."""

    def blocked_request(*args, **kwargs):
        raise AssertionError("network access is blocked in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked_request, raising=True)


@pytest.fixture()
def base_config() -> Config:
    """Build a reusable in-memory configuration."""

    return Config(
        openai_api_key="openai-test-key",
        cohere_api_key="cohere-test-key",
        news_api_key="news-test-key",
        environment="development",
        max_retries=1,
        request_timeout=3.0,
        daily_budget=5.0,
    )


class FakeResponse:
    """Minimal response object for NewsAPI tests."""

    def __init__(self, status_code: int, payload: object | None = None, *, json_error: Exception | None = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        self.headers = headers or {}

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class FakeSession:
    """Sequence-driven session stub for NewsAPI tests."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if not self.responses:
            raise AssertionError("unexpected extra NewsAPI call")
        next_item = self.responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


class FakeRateLimiter:
    """Rate limiter stub that records wait calls without sleeping."""

    def __init__(self, name: str, waits: list[str]) -> None:
        self.name = name
        self._waits = waits

    def wait(self) -> float:
        self._waits.append(self.name)
        return 0.0


class ScriptedAdapter:
    """Provider adapter stub that returns scripted raw responses."""

    def __init__(self, provider: str, model: str, pricing: PricingSpec, responses: list[object]) -> None:
        self._provider = provider
        self._model = model
        self._pricing = pricing
        self._responses = list(responses)
        self.request_calls: list[dict[str, object]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def pricing(self) -> PricingSpec:
        return self._pricing

    def request(self, context):
        self.request_calls.append(
            {
                "prompt": context.prompt,
                "system_prompt": context.system_prompt,
                "max_output_tokens": context.max_output_tokens,
            }
        )
        if not self._responses:
            raise AssertionError(f"unexpected extra {self._provider} request")
        next_item = self._responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item

    def extract_usage(self, response):
        return response.usage.input_tokens, response.usage.output_tokens

    def extract_text(self, response):
        return response.text


class ScriptedLLM:
    """LLM stub that simulates primary/fallback behavior and validation."""

    def __init__(self, scripts: list[list[dict[str, object]]]) -> None:
        self.scripts = list(scripts)
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        task,
        *,
        primary_provider,
        fallback_provider,
        system_prompt,
        max_output_tokens,
        result_validator=None,
        attempt_hook=None,
        service=None,
        config=None,
    ):
        if not self.scripts:
            raise AssertionError("unexpected extra summarizer call")
        script = self.scripts.pop(0)
        self.calls.append(
            {
                "task": task,
                "primary_provider": primary_provider,
                "fallback_provider": fallback_provider,
                "system_prompt": system_prompt,
                "max_output_tokens": max_output_tokens,
            }
        )
        last_error = None
        for attempt in script:
            result = LLMResult(
                text=attempt["text"],
                provider=attempt["provider"],
                model=attempt["model"],
                input_tokens=attempt["input_tokens"],
                output_tokens=attempt["output_tokens"],
                estimated_cost_usd=attempt["cost"],
            )
            if attempt_hook is not None:
                attempt_hook(result)
            try:
                if result_validator is not None:
                    result_validator(result)
            except Exception as exc:
                last_error = exc
                continue
            return result
        raise LLMProviderError(str(last_error) if last_error is not None else "Both providers failed.")


def make_article(title: str, *, url: str, description: str | None = "desc", content: str | None = "content", source_name: str = "Example Source") -> NewsArticle:
    """Create a stable article fixture."""

    raw = {
        "source": {"id": "example", "name": source_name},
        "title": title,
        "description": description,
        "content": content,
        "url": url,
        "publishedAt": "2026-10-20T00:00:00Z",
    }
    return NewsArticle(
        source={"id": "example", "name": source_name},
        author=None,
        title=title,
        description=description,
        url=url,
        url_to_image=None,
        published_at="2026-10-20T00:00:00Z",
        content=content,
        raw=raw,
    )


def make_summary_article(title: str = "Headline", *, description: str | None = "Short description", content: str | None = "Extended content") -> NewsArticle:
    return make_article(title, url=f"https://example.com/{title.lower().replace(' ', '-')}", description=description, content=content)


def make_config(*, max_retries: int = 1, daily_budget: float = 5.0) -> Config:
    return Config(
        openai_api_key="openai-test-key",
        cohere_api_key="cohere-test-key",
        news_api_key="news-test-key",
        environment="development",
        max_retries=max_retries,
        request_timeout=3.0,
        daily_budget=daily_budget,
    )


# --- Config tests ---------------------------------------------------------


def test_get_config_reads_values_and_keeps_repr_safe():
    config = get_config(
        environ={
            "OPENAI_API_KEY": "openai-secret",
            "COHERE_API_KEY": "cohere-secret",
            "NEWS_API_KEY": "news-secret",
            "ENVIRONMENT": "staging",
            "MAX_RETRIES": "4",
            "REQUEST_TIMEOUT": "12.5",
            "DAILY_BUDGET": "7.50",
        },
        load_dotenv_file=False,
    )
    assert config.environment == "staging"
    assert config.max_retries == 4
    assert config.request_timeout == 12.5
    assert config.daily_budget == 7.5
    safe_repr = repr(config)
    assert "openai-secret" not in safe_repr
    assert "cohere-secret" not in safe_repr
    assert "news-secret" not in safe_repr


@pytest.mark.parametrize(
    "environ,expected_fragments",
    [
        ({"OPENAI_API_KEY": "one"}, ["COHERE_API_KEY", "NEWS_API_KEY"]),
        ({"COHERE_API_KEY": "two"}, ["OPENAI_API_KEY", "NEWS_API_KEY"]),
        ({"NEWS_API_KEY": "three"}, ["OPENAI_API_KEY", "COHERE_API_KEY"]),
    ],
)
def test_get_config_reports_all_missing_keys(environ, expected_fragments):
    with pytest.raises(ConfigError) as exc_info:
        get_config(environ=environ, load_dotenv_file=False)
    message = str(exc_info.value)
    for fragment in expected_fragments:
        assert fragment in message
    for value in environ.values():
        assert value not in message


@pytest.mark.parametrize(
    "key,value,expected_fragment",
    [
        ("MAX_RETRIES", "-1", "MAX_RETRIES"),
        ("REQUEST_TIMEOUT", "0", "REQUEST_TIMEOUT"),
        ("DAILY_BUDGET", "nan", "DAILY_BUDGET"),
    ],
)
def test_get_config_rejects_invalid_numbers(key, value, expected_fragment):
    environ = {
        "OPENAI_API_KEY": "openai",
        "COHERE_API_KEY": "cohere",
        "NEWS_API_KEY": "news",
        "ENVIRONMENT": "development",
        "MAX_RETRIES": "3",
        "REQUEST_TIMEOUT": "30",
        "DAILY_BUDGET": "5.00",
    }
    environ[key] = value
    with pytest.raises(ConfigError) as exc_info:
        get_config(environ=environ, load_dotenv_file=False)
    assert expected_fragment in str(exc_info.value)


# --- NewsAPI tests --------------------------------------------------------


def test_newsapi_success_preserves_raw_and_reports_diagnostics(base_config):
    raw_article = {
        "source": {"id": "example", "name": "Example Source"},
        "title": "Technology update",
        "description": "Short description",
        "content": "Full-ish content",
        "url": "https://example.com/tech",
        "publishedAt": "2026-10-20T00:00:00Z",
    }
    session = FakeSession([FakeResponse(200, {"status": "ok", "articles": [raw_article]})])
    diagnostics: list[NewsFetchDiagnostics] = []

    articles = fetch_top_headlines(
        config=base_config,
        session=session,
        sleep_fn=lambda _: None,
        random_fn=lambda: 0.0,
        diagnostics_hook=diagnostics.append,
    )

    assert len(articles) == 1
    assert articles[0].raw == raw_article
    assert session.calls[0]["headers"] == {"X-Api-Key": base_config.news_api_key}
    assert diagnostics[0].received_count == 1
    assert diagnostics[0].kept_count == 1
    assert diagnostics[0].discarded_count == 0


def test_newsapi_empty_output_returns_empty_list(base_config):
    session = FakeSession([FakeResponse(200, {"status": "ok", "articles": []})])
    articles = fetch_top_headlines(config=base_config, session=session, sleep_fn=lambda _: None, random_fn=lambda: 0.0)
    assert articles == []
    assert len(session.calls) == 1


def test_newsapi_skips_removed_title_and_keeps_valid_article(base_config):
    removed = {
        "source": {"name": "Example Source"},
        "title": "[removed]",
        "description": "Discarded description",
        "content": "Discarded content",
        "url": "https://example.com/removed",
    }
    valid = {
        "source": {"name": "Example Source"},
        "title": "Working article",
        "description": "Useful description",
        "content": "Useful content",
        "url": "https://example.com/valid",
    }
    session = FakeSession([FakeResponse(200, {"status": "ok", "articles": [removed, valid]})])
    diagnostics: list[NewsFetchDiagnostics] = []

    articles = fetch_top_headlines(
        config=base_config,
        session=session,
        sleep_fn=lambda _: None,
        random_fn=lambda: 0.0,
        diagnostics_hook=diagnostics.append,
    )

    assert [article.title for article in articles] == ["Working article"]
    assert diagnostics[0].discard_reasons == {"title_unusable": 1}


def test_newsapi_401_does_not_retry(base_config):
    session = FakeSession([
        FakeResponse(401, {"status": "error", "code": "apiKeyInvalid", "message": "invalid"}),
    ])

    with pytest.raises(NewsAPIError) as exc_info:
        fetch_top_headlines(config=base_config, session=session, sleep_fn=lambda _: None, random_fn=lambda: 0.0)

    assert len(session.calls) == 1
    message = str(exc_info.value)
    assert "HTTP 401" in message
    assert "apiKeyInvalid" in message


def test_newsapi_timeout_then_success_retries_once(base_config):
    session = FakeSession([
        Timeout(),
        FakeResponse(200, {"status": "ok", "articles": []}),
    ])
    sleep_calls: list[float] = []

    articles = fetch_top_headlines(
        config=base_config,
        session=session,
        sleep_fn=sleep_calls.append,
        random_fn=lambda: 0.0,
    )

    assert articles == []
    assert len(session.calls) == 2
    assert sleep_calls == [1.0]


def test_newsapi_timeout_exhausts_retries(base_config):
    config = make_config(max_retries=1)
    session = FakeSession([Timeout(), Timeout()])
    sleep_calls: list[float] = []

    with pytest.raises(NewsAPIError):
        fetch_top_headlines(config=config, session=session, sleep_fn=sleep_calls.append, random_fn=lambda: 0.0)

    assert len(session.calls) == 2
    assert sleep_calls == [1.0]


def test_newsapi_invalid_json_raises_safe_error(base_config):
    session = FakeSession([FakeResponse(200, None, json_error=ValueError("bad json"))])

    with pytest.raises(NewsAPIError) as exc_info:
        fetch_top_headlines(config=base_config, session=session, sleep_fn=lambda _: None, random_fn=lambda: 0.0)

    assert "invalid JSON" in str(exc_info.value)


# --- Adapter tests --------------------------------------------------------


def test_openai_adapter_extracts_usage_and_text(base_config):
    adapter = OpenAIAdapter(
        base_config,
        client=object(),
        pricing=PricingSpec(
            provider="openai",
            model="gpt-4o-mini",
            input_cost_per_million=Decimal("0.15"),
            output_cost_per_million=Decimal("0.60"),
            source="test",
            checked_on=date(2026, 10, 20),
        ),
    )
    response = SimpleNamespace(
        output_text="  concise answer  ",
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )

    assert adapter.extract_usage(response) == (11, 7)
    assert adapter.extract_text(response) == "concise answer"


def test_cohere_adapter_extracts_usage_and_text(base_config):
    adapter = CohereAdapter(
        base_config,
        client=object(),
        pricing=PricingSpec(
            provider="cohere",
            model="command-r7b-12-2024",
            input_cost_per_million=Decimal("0.0375"),
            output_cost_per_million=Decimal("0.15"),
            source="test",
            checked_on=date(2026, 10, 20),
        ),
    )
    response = SimpleNamespace(
        message=SimpleNamespace(
            content=[SimpleNamespace(text=" first "), {"text": "second"}],
        ),
        usage=SimpleNamespace(billed_units=SimpleNamespace(input_tokens=9, output_tokens=4)),
    )

    assert adapter.extract_usage(response) == (9, 4)
    assert adapter.extract_text(response) == "first\nsecond"


# --- LLM service tests ----------------------------------------------------


def make_service(tmp_path: Path, *, max_retries: int = 1, daily_budget: float = 5.0, openai_responses: list[object] | None = None, cohere_responses: list[object] | None = None, waits: list[str] | None = None, sleep_calls: list[float] | None = None) -> tuple[LLMService, ScriptedAdapter, ScriptedAdapter]:
    openai_responses = list(openai_responses or [])
    cohere_responses = list(cohere_responses or [])
    waits = waits if waits is not None else []
    sleep_calls = sleep_calls if sleep_calls is not None else []
    config = make_config(max_retries=max_retries, daily_budget=daily_budget)
    openai_adapter = ScriptedAdapter(
        "openai",
        "gpt-4o-mini",
        PricingSpec("openai", "gpt-4o-mini", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
        openai_responses,
    )
    cohere_adapter = ScriptedAdapter(
        "cohere",
        "command-r7b-12-2024",
        PricingSpec("cohere", "command-r7b-12-2024", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
        cohere_responses,
    )
    service = LLMService(
        config,
        openai_adapter=openai_adapter,
        cohere_adapter=cohere_adapter,
        budget_ledger=BudgetLedger(Decimal(str(daily_budget)), path=tmp_path / "budget.json"),
        rate_limiters={"openai": FakeRateLimiter("openai", waits), "cohere": FakeRateLimiter("cohere", waits)},
        sleep_fn=sleep_calls.append,
        random_fn=lambda: 0.0,
        log_fn=lambda *_: None,
    )
    return service, openai_adapter, cohere_adapter


def make_raw_llm_response(*, text: str, input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        text=text,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_llm_fallback_openai_to_cohere_counts_invalid_attempt_once(tmp_path):
    service, openai_adapter, cohere_adapter = make_service(
        tmp_path,
        openai_responses=[make_raw_llm_response(text="", input_tokens=1, output_tokens=1)],
        cohere_responses=[make_raw_llm_response(text="valid answer", input_tokens=1, output_tokens=1)],
    )
    attempts: list[LLMResult] = []

    result = service.ask_with_fallback(
        "task",
        primary_provider="openai",
        fallback_provider="cohere",
        result_validator=lambda response: (_ for _ in ()).throw(ValueError("invalid")) if not response.text.strip() else None,
        attempt_hook=attempts.append,
    )

    assert result.provider == "cohere"
    assert result.text == "valid answer"
    assert len(attempts) == 2
    assert openai_adapter.request_calls == [{"prompt": "task", "system_prompt": None, "max_output_tokens": 256}]
    assert cohere_adapter.request_calls == [{"prompt": "task", "system_prompt": None, "max_output_tokens": 256}]
    assert service.budget_status.spent_usd == Decimal("0.000004")


def test_llm_fallback_cohere_to_openai(tmp_path):
    service, openai_adapter, cohere_adapter = make_service(
        tmp_path,
        openai_responses=[make_raw_llm_response(text="valid answer", input_tokens=1, output_tokens=1)],
        cohere_responses=[make_raw_llm_response(text="", input_tokens=1, output_tokens=1)],
    )

    result = service.ask_with_fallback(
        "task",
        primary_provider="cohere",
        fallback_provider="openai",
        result_validator=lambda response: (_ for _ in ()).throw(ValueError("invalid")) if not response.text.strip() else None,
    )

    assert result.provider == "openai"
    assert result.text == "valid answer"
    assert cohere_adapter.request_calls == [{"prompt": "task", "system_prompt": None, "max_output_tokens": 256}]
    assert openai_adapter.request_calls == [{"prompt": "task", "system_prompt": None, "max_output_tokens": 256}]


def test_llm_both_providers_fail(tmp_path):
    service, _, _ = make_service(
        tmp_path,
        openai_responses=[make_raw_llm_response(text="", input_tokens=1, output_tokens=1)],
        cohere_responses=[make_raw_llm_response(text="", input_tokens=1, output_tokens=1)],
    )

    with pytest.raises(LLMProviderError):
        service.ask_with_fallback(
            "task",
            primary_provider="openai",
            fallback_provider="cohere",
            result_validator=lambda response: (_ for _ in ()).throw(ValueError("invalid")) if not response.text.strip() else None,
        )


def test_llm_retries_rate_limit_and_sleep_without_real_wait(tmp_path):
    service, openai_adapter, _ = make_service(
        tmp_path,
        max_retries=2,
        openai_responses=[TimeoutError(), TimeoutError(), make_raw_llm_response(text="ok", input_tokens=1, output_tokens=1)],
    )
    attempts: list[LLMResult] = []
    sleep_calls: list[float] = []
    service._sleep = sleep_calls.append  # type: ignore[attr-defined]

    result = service.ask_with_fallback("task", primary_provider="openai", fallback_provider="cohere", attempt_hook=attempts.append)

    assert result.provider == "openai"
    assert len(openai_adapter.request_calls) == 3
    assert attempts[-1].text == "ok"
    assert sleep_calls == [1.0, 2.0]


def test_llm_budget_persists_between_instances_and_blocks_without_fallback(tmp_path):
    config = make_config(daily_budget=0.000289)
    budget_path = tmp_path / "budget.json"
    response = make_raw_llm_response(text="ok", input_tokens=33, output_tokens=256)
    ledger = BudgetLedger(Decimal("0.000289"), path=budget_path)

    service_one = LLMService(
        config,
        openai_adapter=ScriptedAdapter(
            "openai",
            "gpt-4o-mini",
            PricingSpec("openai", "gpt-4o-mini", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
            [response],
        ),
        cohere_adapter=ScriptedAdapter(
            "cohere",
            "command-r7b-12-2024",
            PricingSpec("cohere", "command-r7b-12-2024", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
            [],
        ),
        budget_ledger=ledger,
        rate_limiters={"openai": FakeRateLimiter("openai", []), "cohere": FakeRateLimiter("cohere", [])},
        sleep_fn=lambda _: None,
        random_fn=lambda: 0.0,
        log_fn=lambda *_: None,
    )

    service_one.ask_with_fallback("x", primary_provider="openai", fallback_provider="cohere")
    assert service_one.budget_status.spent_usd == Decimal("0.000289")

    openai_adapter_two = ScriptedAdapter(
        "openai",
        "gpt-4o-mini",
        PricingSpec("openai", "gpt-4o-mini", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
        [response],
    )
    service_two = LLMService(
        config,
        openai_adapter=openai_adapter_two,
        cohere_adapter=ScriptedAdapter(
            "cohere",
            "command-r7b-12-2024",
            PricingSpec("cohere", "command-r7b-12-2024", Decimal("1"), Decimal("1"), "test", date(2026, 10, 20)),
            [],
        ),
        budget_ledger=BudgetLedger(Decimal("0.000289"), path=budget_path),
        rate_limiters={"openai": FakeRateLimiter("openai", []), "cohere": FakeRateLimiter("cohere", [])},
        sleep_fn=lambda _: None,
        random_fn=lambda: 0.0,
        log_fn=lambda *_: None,
    )

    with pytest.raises(BudgetExceededError):
        service_two.ask_with_fallback("x", primary_provider="openai", fallback_provider="cohere")
    assert openai_adapter_two.request_calls == []


def test_llm_budget_resets_on_new_day(monkeypatch, tmp_path):
    import llm_providers as providers

    budget_path = tmp_path / "budget.json"
    budget_path.write_text('{"day": "2026-10-19", "spent_usd": "1.250000"}', encoding="utf-8")
    monkeypatch.setattr(providers, "_today_key", lambda: "2026-10-20")

    ledger = BudgetLedger(Decimal("5.0"), path=budget_path)
    assert ledger.status.day == "2026-10-20"
    assert ledger.status.spent_usd == Decimal("0")

# --- Summarizer tests -----------------------------------------------------


def test_collect_articles_separates_actual_discards_from_limit_skips():
    articles = [
        make_article("One", url="https://example.com/one"),
        make_article("Two", url="https://example.com/two"),
        make_article("Three", url="https://example.com/three"),
        make_article("Four", url="https://example.com/four"),
    ]

    def source(**kwargs):
        diagnostics_hook = kwargs.get("diagnostics_hook")
        if diagnostics_hook is not None:
            diagnostics_hook(NewsFetchDiagnostics(requested_page_size=5, received_count=4, kept_count=4, discarded_count=0, discard_reasons={}))
        return articles

    summarizer = NewsSummarizer(config=make_config(), news_source=source, llm_ask=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called")), log_fn=lambda *_: None)
    selected, report = summarizer.collect_articles(limit=2)

    assert [article.url for article in selected] == ["https://example.com/one", "https://example.com/two"]
    assert report.received == 4
    assert report.discarded == 0
    assert report.not_selected_due_to_limit == 2
    assert report.discard_reasons == {}


def test_collect_articles_reports_duplicate_urls_and_limit_skips():
    articles = [
        make_article("One", url="https://example.com/one"),
        make_article("Duplicate", url="https://example.com/one"),
        make_article("Two", url="https://example.com/two"),
        make_article("Three", url="https://example.com/three"),
    ]

    def source(**kwargs):
        diagnostics_hook = kwargs.get("diagnostics_hook")
        if diagnostics_hook is not None:
            diagnostics_hook(NewsFetchDiagnostics(requested_page_size=5, received_count=4, kept_count=4, discarded_count=0, discard_reasons={}))
        return articles

    summarizer = NewsSummarizer(config=make_config(), news_source=source, llm_ask=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called")), log_fn=lambda *_: None)
    selected, report = summarizer.collect_articles(limit=2)

    assert [article.url for article in selected] == ["https://example.com/one", "https://example.com/two"]
    assert report.discarded == 1
    assert report.not_selected_due_to_limit == 1
    assert report.discard_reasons == {"duplicate_url": 1}


def test_summarizer_passes_exact_summary_to_sentiment_stage():
    article = make_summary_article("Chip launch")
    scripted = ScriptedLLM(
        [
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "Short factual summary.", "input_tokens": 9, "output_tokens": 3, "cost": Decimal("0.0010")},
            ],
            [
                {"provider": "cohere", "model": "command-r7b-12-2024", "text": " neutral ", "input_tokens": 8, "output_tokens": 1, "cost": Decimal("0.0004")},
            ],
        ]
    )
    summarizer = NewsSummarizer(config=make_config(), news_source=lambda **kwargs: [article], llm_ask=scripted, log_fn=lambda *_: None)

    record = summarizer.process_article(article, index=1)

    assert record["status"] == "ok"
    assert record["summary"] == "Short factual summary."
    assert record["sentiment"] == "neutral"
    assert "Short factual summary." in scripted.calls[1]["task"]
    assert record["cost_usd"] == Decimal("0.0014")


def test_summarizer_marks_title_only_limitations():
    article = make_summary_article("Title only", description=None, content=None)
    scripted = ScriptedLLM(
        [
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "Title-only summary.", "input_tokens": 5, "output_tokens": 2, "cost": Decimal("0.0010")},
            ],
            [
                {"provider": "cohere", "model": "command-r7b-12-2024", "text": "positive", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0004")},
            ],
        ]
    )
    summarizer = NewsSummarizer(config=make_config(), news_source=lambda **kwargs: [article], llm_ask=scripted, log_fn=lambda *_: None)

    record = summarizer.process_article(article, index=1)

    assert record["status"] == "ok"
    assert record["limitations"] == ["Only the title was available."]
    assert "Limitation: only the title is available." in scripted.calls[0]["task"]


def test_summarizer_does_not_turn_invalid_sentiment_into_neutral():
    article = make_summary_article("Validation article")
    scripted = ScriptedLLM(
        [
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "Summary text.", "input_tokens": 6, "output_tokens": 2, "cost": Decimal("0.0010")},
            ],
            [
                {"provider": "cohere", "model": "command-r7b-12-2024", "text": "maybe", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0004")},
                {"provider": "openai", "model": "gpt-4o-mini", "text": "negative", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0005")},
            ],
        ]
    )
    summarizer = NewsSummarizer(config=make_config(), news_source=lambda **kwargs: [article], llm_ask=scripted, log_fn=lambda *_: None)

    record = summarizer.process_article(article, index=1)

    assert record["status"] == "ok"
    assert record["sentiment"] == "negative"
    assert record["sentiment_stage"]["provider"] == "openai"


def test_summarizer_keeps_other_articles_when_one_fails():
    first = make_summary_article("First article")
    second = make_summary_article("Second article")
    scripted = ScriptedLLM(
        [
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "First summary.", "input_tokens": 5, "output_tokens": 2, "cost": Decimal("0.0010")},
            ],
            [
                {"provider": "cohere", "model": "command-r7b-12-2024", "text": "positive", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0004")},
            ],
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0010")},
            ],
        ]
    )
    summarizer = NewsSummarizer(config=make_config(), news_source=lambda **kwargs: [first, second], llm_ask=scripted, log_fn=lambda *_: None)

    results = summarizer.process_articles([first, second])

    assert len(results) == 2
    assert results[0]["status"] == "ok"
    assert results[1]["status"] == "error"
    assert results[1]["error_stage"] == "summary"


def test_summarizer_stops_when_budget_is_exhausted():
    first = make_summary_article("First article")
    second = make_summary_article("Second article")

    class BudgetStoppingLLM(ScriptedLLM):
        def __call__(self, task, *, primary_provider, fallback_provider, system_prompt, max_output_tokens, result_validator=None, attempt_hook=None, service=None, config=None):
            if primary_provider == "openai" and "Second" in task:
                raise BudgetExceededError("budget exhausted")
            return super().__call__(task, primary_provider=primary_provider, fallback_provider=fallback_provider, system_prompt=system_prompt, max_output_tokens=max_output_tokens, result_validator=result_validator, attempt_hook=attempt_hook, service=service, config=config)

    budget_scripted = BudgetStoppingLLM(
        [
            [
                {"provider": "openai", "model": "gpt-4o-mini", "text": "First summary.", "input_tokens": 5, "output_tokens": 2, "cost": Decimal("0.0010")},
            ],
            [
                {"provider": "cohere", "model": "command-r7b-12-2024", "text": "positive", "input_tokens": 5, "output_tokens": 1, "cost": Decimal("0.0004")},
            ],
        ]
    )
    summarizer = NewsSummarizer(config=make_config(), news_source=lambda **kwargs: [first, second], llm_ask=budget_scripted, log_fn=lambda *_: None)

    results = summarizer.process_articles([first, second, make_summary_article("Third article")])

    assert len(results) == 2
    assert results[-1]["status"] == "error"
    assert results[-1]["error_stage"] == "budget"


def test_summarizer_collect_articles_returns_actual_selection_counts_without_llm():
    articles = [
        make_article("One", url="https://example.com/one"),
        make_article("Two", url="https://example.com/two"),
        make_article("Three", url="https://example.com/three"),
        make_article("Four", url="https://example.com/four"),
    ]

    def source(**kwargs):
        diagnostics_hook = kwargs.get("diagnostics_hook")
        if diagnostics_hook is not None:
            diagnostics_hook(NewsFetchDiagnostics(requested_page_size=5, received_count=4, kept_count=4, discarded_count=0, discard_reasons={}))
        return articles

    log_lines: list[str] = []
    summarizer = NewsSummarizer(config=make_config(), news_source=source, llm_ask=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called")), log_fn=log_lines.append)
    selected, report = summarizer.collect_articles(limit=2)

    assert report.discarded == 0
    assert report.not_selected_due_to_limit == 2
    assert "not_selected_due_to_limit=2" in log_lines[0]
    assert len(selected) == 2
