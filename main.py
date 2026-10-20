"""Console entry point for the multi-provider news summarizer lab."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

from config import ConfigError
from llm_providers import BudgetExceededError, LLMProviderError
from news_api import NewsAPIError
from summarizer import NewsSummarizer

DEFAULT_CATEGORY = "technology"
DEFAULT_COUNT = 3
MIN_COUNT = 3
MAX_COUNT = 5


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    """Paths used to store one CLI run evidence bundle."""

    run_id: str
    timestamp: str
    inputs: Path
    outputs: Path
    trace: Path


def main(
    argv: list[str] | None = None,
    *,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    summarizer_factory: Callable[..., NewsSummarizer] = NewsSummarizer,
    evidence_dir: Path | str = Path("evidence"),
) -> int:
    """Run the command-line summarizer workflow."""

    parsed = _parse_args(argv)
    category = _resolve_category(parsed.category, input_fn=input_fn, print_fn=print_fn, interactive=parsed.interactive)
    if category is None:
        return 2
    count = _resolve_count(parsed.count, input_fn=input_fn, print_fn=print_fn, interactive=parsed.interactive)
    if count is None:
        return 2

    run_id = uuid.uuid4().hex[:8]
    started_at = datetime.now().astimezone()
    timestamp = started_at.strftime("%Y%m%dT%H%M%S%z")
    trace_lines: list[str] = []

    def emit(message: str) -> None:
        line = _safe_message(message)
        trace_lines.append(line)
        print_fn(line)

    emit(f"run_id={run_id} started_at={started_at.isoformat(timespec='seconds')}")
    emit(f"request category={category} count={count}")

    results: list[dict[str, Any]] = []
    selected_raw_payloads: list[Any] = []
    selection_report: dict[str, Any] | None = None
    failure_message: str | None = None
    summary_message: str | None = None
    exit_code = 0
    summarizer: Any | None = None

    try:
        summarizer = summarizer_factory(log_fn=emit)
        selected_articles, report = summarizer.collect_articles(category=category, country="us", limit=count)
        selection_report = {
            "requested": report.requested,
            "received": report.received,
            "discarded": report.discarded,
            "selected": report.selected,
            "not_selected_due_to_limit": report.not_selected_due_to_limit,
            "discard_reasons": dict(report.discard_reasons),
        }
        selected_raw_payloads = [article.raw for article in selected_articles]
        results = summarizer.process_articles(selected_articles)
    except (ConfigError, NewsAPIError, LLMProviderError, BudgetExceededError, ValueError) as exc:
        failure_message = _safe_message(exc)
        exit_code = 1
        emit(f"run_status=error message={failure_message}")
    except KeyboardInterrupt:
        failure_message = "Interrupted by user."
        exit_code = 130
        emit("run_status=interrupted message=Interrupted by user.")
    except EOFError:
        failure_message = "Input ended before the run could start."
        exit_code = 2
        emit("run_status=aborted message=Input ended before the run could start.")
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        failure_message = "Unexpected error while running the CLI."
        exit_code = 1
        emit(f"run_status=error message={_safe_message(exc)}")

    success_count = sum(1 for record in results if record.get("status") == "ok")
    error_count = len(results) - success_count
    run_cost = _sum_known_costs(record.get("cost_usd") for record in results)
    daily_spend = _read_daily_spend(summarizer)
    full_success = selection_report is not None and selection_report["selected"] == count and error_count == 0 and len(results) == count
    if selection_report is not None and selection_report["selected"] < count:
        summary_message = f"Only {selection_report['selected']} unique articles were available out of requested {count}."
        exit_code = 1 if exit_code == 0 else exit_code
    elif error_count > 0 and exit_code == 0:
        summary_message = "One or more articles failed during processing."
        exit_code = 1
    elif exit_code == 0 and not full_success:
        summary_message = "The run did not complete successfully."
        exit_code = 1

    _print_results(
        print_fn,
        results=results,
        success_count=success_count,
        error_count=error_count,
        run_cost=run_cost,
        daily_spend=daily_spend,
        category=category,
        count=count,
        summary_message=summary_message,
        failure_message=failure_message,
        selection_report=selection_report,
    )

    evidence_status = _write_evidence_bundle(
        evidence_dir=Path(evidence_dir),
        evidence=EvidencePaths(
            run_id=run_id,
            timestamp=timestamp,
            inputs=Path(evidence_dir) / f"{timestamp}_{run_id}_inputs.json",
            outputs=Path(evidence_dir) / f"{timestamp}_{run_id}_outputs.json",
            trace=Path(evidence_dir) / f"{timestamp}_{run_id}_trace.txt",
        ),
        category=category,
        count=count,
        results=results,
        selected_raw_payloads=selected_raw_payloads,
        trace_lines=trace_lines,
        selection_report=selection_report,
        run_cost=run_cost,
        daily_spend=daily_spend,
        failure_message=failure_message,
    )
    if not evidence_status:
        print_fn("evidence_status=error message=Failed to save CLI evidence.")
        exit_code = exit_code or 1
    else:
        print_fn("evidence_status=ok")

    return exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments while keeping the module import-safe."""

    parser = argparse.ArgumentParser(prog="main.py")
    parser.add_argument("--category")
    parser.add_argument("--count")
    parsed = parser.parse_args(argv)
    parsed.interactive = len(sys.argv[1:]) == 0 if argv is None else len(argv) == 0
    return parsed


def _resolve_category(
    value: str | None,
    *,
    input_fn: Callable[[str], str],
    print_fn: Callable[[str], None],
    interactive: bool,
) -> str | None:
    """Resolve the requested news category."""

    if value is not None:
        category = value.strip() or DEFAULT_CATEGORY
        return category
    if not interactive:
        return DEFAULT_CATEGORY
    while True:
        try:
            raw = input_fn(f"Category [{DEFAULT_CATEGORY}]: ")
        except EOFError:
            return None
        category = raw.strip() or DEFAULT_CATEGORY
        if category:
            return category
        print_fn(f"Invalid category. Use a non-empty value or press Enter for {DEFAULT_CATEGORY}.")


def _resolve_count(
    value: str | None,
    *,
    input_fn: Callable[[str], str],
    print_fn: Callable[[str], None],
    interactive: bool,
) -> int | None:
    """Resolve the requested article count."""

    if value is not None:
        try:
            return _parse_count(value)
        except ValueError as exc:
            print_fn(_safe_message(exc))
            return None
    if not interactive:
        return DEFAULT_COUNT
    while True:
        try:
            raw = input_fn(f"Article count [{MIN_COUNT}-{MAX_COUNT}] (default {DEFAULT_COUNT}): ")
        except EOFError:
            return None
        if not raw.strip():
            return DEFAULT_COUNT
        try:
            return _parse_count(raw)
        except ValueError as exc:
            print_fn(_safe_message(exc))


def _parse_count(raw: str) -> int:
    """Validate the article count."""

    try:
        count = int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"count must be an integer between {MIN_COUNT} and {MAX_COUNT}") from exc
    if count < MIN_COUNT or count > MAX_COUNT:
        raise ValueError(f"count must be between {MIN_COUNT} and {MAX_COUNT}")
    return count


def _print_results(
    print_fn: Callable[[str], None],
    *,
    results: list[dict[str, Any]],
    success_count: int,
    error_count: int,
    run_cost: Decimal | None,
    daily_spend: Decimal | None,
    category: str,
    count: int,
    summary_message: str | None,
    failure_message: str | None,
    selection_report: dict[str, Any] | None,
) -> None:
    """Render a safe summary of the CLI run."""

    print_fn(f"requested_category={category}")
    print_fn(f"requested_count={count}")
    if selection_report is not None:
        print_fn(
            "news_selection "
            f"requested={selection_report['requested']} received={selection_report['received']} "
            f"discarded={selection_report['discarded']} selected={selection_report['selected']} "
            f"not_selected_due_to_limit={selection_report['not_selected_due_to_limit']} "
            f"discard_reasons={selection_report['discard_reasons']}"
        )
    for index, result in enumerate(results, start=1):
        print_fn(f"[{index}] status={result.get('status')} title={result.get('title')}")
        print_fn(f"    source={result.get('source')} url={result.get('url')}")
        print_fn(f"    summary={result.get('summary')}")
        print_fn(f"    sentiment={result.get('sentiment')}")
        print_fn(f"    limitations={_render_limitations(result.get('limitations'))}")
        print_fn(f"    summary_provider={_render_stage_provider(result.get('summary_stage'))}")
        print_fn(f"    sentiment_provider={_render_stage_provider(result.get('sentiment_stage'))}")
        print_fn(f"    cost_usd={_fmt_decimal(result.get('cost_usd'))}")
        if result.get("status") != "ok":
            print_fn(f"    error_stage={result.get('error_stage')}")
            print_fn(f"    error_message={result.get('error_message')}")
    print_fn(f"success_count={success_count}")
    print_fn(f"error_count={error_count}")
    print_fn(f"run_cost_usd={_fmt_decimal(run_cost)}")
    print_fn(f"daily_spend_usd={_fmt_decimal(daily_spend)}")
    if summary_message is not None:
        print_fn(summary_message)
    if failure_message is not None:
        print_fn(f"run_message={failure_message}")


def _write_evidence_bundle(
    *,
    evidence_dir: Path,
    evidence: EvidencePaths,
    category: str,
    count: int,
    results: list[dict[str, Any]],
    selected_raw_payloads: list[Any],
    trace_lines: list[str],
    selection_report: dict[str, Any] | None,
    run_cost: Decimal | None,
    daily_spend: Decimal | None,
    failure_message: str | None,
) -> bool:
    """Persist safe evidence files for later lab proof."""

    try:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        selected_payload = {
            "category": category,
            "count": count,
            "selection_report": selection_report,
            "articles": selected_raw_payloads,
        }
        output_payload = {
            "category": category,
            "count": count,
            "results": results,
            "run_cost_usd": run_cost,
            "daily_spend_usd": daily_spend,
            "failure_message": failure_message,
        }
        trace_payload = list(trace_lines)
        if selection_report is not None:
            trace_payload.append(f"selection_report={selection_report}")
        trace_payload.append(f"run_cost_usd={_fmt_decimal(run_cost)}")
        trace_payload.append(f"daily_spend_usd={_fmt_decimal(daily_spend)}")
        _atomic_write_json(evidence.inputs, selected_payload)
        _atomic_write_json(evidence.outputs, output_payload)
        _atomic_write_text(evidence.trace, "\n".join(trace_payload) + "\n")
        return True
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically using UTF-8 text."""

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temp_path.replace(path)


def _atomic_write_text(path: Path, content: str) -> None:
    """Write text atomically using UTF-8."""

    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _render_limitations(limitations: Any) -> str:
    """Render source limitations as a compact string."""

    if not limitations:
        return "none"
    if isinstance(limitations, Iterable) and not isinstance(limitations, (str, bytes)):
        return "; ".join(str(item) for item in limitations)
    return str(limitations)


def _sum_known_costs(values: Iterable[Any]) -> Decimal | None:
    """Sum costs only when every value is known."""

    total = Decimal("0")
    seen = False
    for value in values:
        if value is None:
            return None
        seen = True
        total += Decimal(str(value))
    return total if seen else None


def _read_daily_spend(summarizer: Any) -> Decimal | None:
    """Read the current daily spend from the active summarizer, if available."""

    if summarizer is None:
        return None
    budget_status = getattr(summarizer, "budget_status", None)
    if budget_status is None:
        return None
    return getattr(budget_status, "spent_usd", None)


def _render_stage_provider(stage: Any) -> str:
    """Render a provider/model pair safely."""

    if not stage:
        return "none"
    return f"{stage.get('provider')} / {stage.get('model')}"


def _fmt_decimal(value: Any) -> str:
    """Render Decimal-like values without rounding."""

    if value is None:
        return "unknown"
    return str(value)


def _safe_message(value: Any) -> str:
    """Convert a value into a safe single-line message."""

    return " ".join(str(value).split())


if __name__ == "__main__":
    raise SystemExit(main())