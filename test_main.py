from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import main as cli


@dataclass(frozen=True)
class FakeArticle:
    """Simple article stub with a raw payload."""

    raw: dict[str, object]


def build_factory(*, selected_count: int, processed_count: int, error_count: int = 0, spent_usd: Decimal = Decimal("1.234567")):
    """Create a deterministic summarizer factory for CLI tests."""

    state = {"instances": [], "collect_calls": [], "process_calls": []}
    selected_articles = [
        FakeArticle(
            raw={
                "source": {"name": f"Source {index}"},
                "title": f"Article {index}",
                "description": f"Description {index}",
                "content": f"Content {index}",
                "url": f"https://example.com/{index}",
            }
        )
        for index in range(selected_count)
    ]
    report = SimpleNamespace(
        requested=5,
        received=selected_count + 2,
        discarded=2,
        selected=selected_count,
        not_selected_due_to_limit=max(0, selected_count - 2),
        discard_reasons={"duplicate_url": 1, "missing_url": 1},
    )
    results: list[dict[str, object]] = []
    for index in range(processed_count):
        is_error = index < error_count
        results.append(
            {
                "status": "error" if is_error else "ok",
                "title": f"Article {index}",
                "source": f"Source {index}",
                "url": f"https://example.com/{index}",
                "summary": f"Summary {index}",
                "sentiment": None if is_error else "positive",
                "limitations": ["NewsAPI content may be truncated."] if index == 0 else [],
                "summary_stage": {"provider": "openai", "model": "gpt-4o-mini"},
                "sentiment_stage": None if is_error else {"provider": "cohere", "model": "command-r"},
                "cost_usd": Decimal("0.001") * (index + 1),
                "error_stage": "sentiment" if is_error else None,
                "error_message": "Invalid sentiment" if is_error else None,
            }
        )

    class FakeSummarizer:
        def __init__(self, *, log_fn=print, **kwargs):
            self.log_fn = log_fn
            self.budget_status = SimpleNamespace(spent_usd=spent_usd)
            state["instances"].append(self)

        def collect_articles(self, *, category: str, country: str, limit: int):
            state["collect_calls"].append({"category": category, "country": country, "limit": limit})
            self.log_fn(
                f"news_selection requested={report.requested} received={report.received} discarded={report.discarded} selected={report.selected} not_selected_due_to_limit={report.not_selected_due_to_limit} discard_reasons={report.discard_reasons}"
            )
            return selected_articles[:selected_count], report

        def process_articles(self, articles):
            article_list = list(articles)
            state["process_calls"].append(article_list)
            return results[: len(article_list)]

    return FakeSummarizer, state, selected_articles, report, results


def make_input(*values: str):
    """Build an input function that returns scripted answers."""

    iterator = iter(values)

    def _input(_prompt: str) -> str:
        return next(iterator)

    return _input


def test_main_uses_defaults_in_interactive_mode(tmp_path: Path):
    factory, state, _articles, _report, _results = build_factory(selected_count=3, processed_count=3)
    lines: list[str] = []

    exit_code = cli.main(
        [],
        input_fn=make_input("", ""),
        print_fn=lines.append,
        summarizer_factory=factory,
        evidence_dir=tmp_path / "evidence",
    )

    assert exit_code == 0
    assert state["collect_calls"] == [{"category": "technology", "country": "us", "limit": 3}]
    assert any(line == "requested_category=technology" for line in lines)
    assert any(line == "requested_count=3" for line in lines)
    assert any(line == "success_count=3" for line in lines)
    evidence_files = sorted((tmp_path / "evidence").iterdir())
    assert len(evidence_files) == 3


def test_main_rejects_invalid_count_argument_without_calls(tmp_path: Path):
    called = {"count": 0}

    def factory(**kwargs):
        called["count"] += 1
        raise AssertionError("summarizer should not be created for invalid arguments")

    lines: list[str] = []
    exit_code = cli.main(["--count", "2"], print_fn=lines.append, summarizer_factory=factory, evidence_dir=tmp_path / "evidence")

    assert exit_code == 2
    assert called["count"] == 0
    assert any("count must be between 3 and 5" in line for line in lines)
    assert not (tmp_path / "evidence").exists()


def test_main_full_success_with_arguments_and_evidence(tmp_path: Path):
    factory, state, _articles, _report, results = build_factory(selected_count=4, processed_count=4)
    lines: list[str] = []

    exit_code = cli.main(
        ["--category", "science", "--count", "4"],
        print_fn=lines.append,
        summarizer_factory=factory,
        evidence_dir=tmp_path / "evidence",
    )

    assert exit_code == 0
    assert state["collect_calls"] == [{"category": "science", "country": "us", "limit": 4}]
    assert any("Article 0" in line for line in lines)
    evidence_dir = tmp_path / "evidence"
    inputs_file = next(evidence_dir.glob("*_inputs.json"))
    outputs_file = next(evidence_dir.glob("*_outputs.json"))
    trace_file = next(evidence_dir.glob("*_trace.txt"))
    inputs_payload = json.loads(inputs_file.read_text(encoding="utf-8"))
    outputs_payload = json.loads(outputs_file.read_text(encoding="utf-8"))
    trace_text = trace_file.read_text(encoding="utf-8")
    assert inputs_payload["count"] == 4
    assert len(inputs_payload["articles"]) == 4
    assert len(outputs_payload["results"]) == 4
    assert outputs_payload["failure_message"] is None
    assert "openai-test-key" not in trace_text
    assert "cohere-test-key" not in trace_text
    assert "news-test-key" not in trace_text
    assert len(results) == 4


def test_main_partial_success_when_not_enough_articles(tmp_path: Path):
    factory, state, _articles, _report, _results = build_factory(selected_count=2, processed_count=2)
    lines: list[str] = []

    exit_code = cli.main(
        ["--category", "technology", "--count", "3"],
        print_fn=lines.append,
        summarizer_factory=factory,
        evidence_dir=tmp_path / "evidence",
    )

    assert exit_code == 1
    assert state["collect_calls"] == [{"category": "technology", "country": "us", "limit": 3}]
    assert any("Only 2 unique articles were available out of requested 3." in line for line in lines)
    assert any("success_count=2" in line for line in lines)
    evidence_dir = tmp_path / "evidence"
    assert len(list(evidence_dir.iterdir())) == 3
    trace_text = next(evidence_dir.glob("*_trace.txt")).read_text(encoding="utf-8")
    assert "run_cost_usd=" in trace_text
    assert "daily_spend_usd=" in trace_text


def test_main_partial_success_on_article_error(tmp_path: Path):
    factory, state, _articles, _report, _results = build_factory(selected_count=3, processed_count=3, error_count=1)
    lines: list[str] = []

    exit_code = cli.main(
        ["--category", "technology", "--count", "3"],
        print_fn=lines.append,
        summarizer_factory=factory,
        evidence_dir=tmp_path / "evidence",
    )

    assert exit_code == 1
    assert state["process_calls"]
    assert any("error_count=1" in line for line in lines)
    assert any("error_stage=sentiment" in line for line in lines)
    outputs_payload = json.loads(next((tmp_path / "evidence").glob("*_outputs.json")).read_text(encoding="utf-8"))
    assert len(outputs_payload["results"]) == 3
    assert outputs_payload["failure_message"] is None