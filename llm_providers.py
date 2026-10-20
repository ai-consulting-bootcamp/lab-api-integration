"""OpenAI and Cohere provider adapters with fallback and budget tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from random import random
from time import monotonic, sleep
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo
import json
import os
import tempfile

from config import Config, get_config

from openai import OpenAI
from openai import APIConnectionError as OpenAIAPIConnectionError
from openai import APIError as OpenAIAPIError
from openai import APIStatusError as OpenAIAPIStatusError
from openai import APITimeoutError as OpenAITimeoutError
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import BadRequestError as OpenAIBadRequestError
from openai import InternalServerError as OpenAIInternalServerError
from openai import PermissionDeniedError as OpenAIPermissionDeniedError
from openai import RateLimitError as OpenAIRateLimitError

import cohere
from cohere import BadRequestError as CohereBadRequestError
from cohere import ForbiddenError as CohereForbiddenError
from cohere import GatewayTimeoutError as CohereGatewayTimeoutError
from cohere import InternalServerError as CohereInternalServerError
from cohere import ServiceUnavailableError as CohereServiceUnavailableError
from cohere import TooManyRequestsError as CohereTooManyRequestsError
from cohere import UnauthorizedError as CohereUnauthorizedError
from cohere import UnprocessableEntityError as CohereUnprocessableEntityError

OPENAI_MODEL = "gpt-4o-mini"
COHERE_MODEL = "command-r7b-12-2024"
OUTPUT_TOKEN_LIMIT = 256
_BUDGET_STATE_FILE = Path(__file__).resolve().with_name(".llm_budget_state.json")
_BUDGET_NOTE = "Sequential single-process usage is supported; parallel processes are not coordinated."
_BERLIN_TZ = ZoneInfo("Europe/Berlin")
_OPENAI_MIN_INTERVAL_SECONDS = 0.5
_COHERE_MIN_INTERVAL_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Normalized LLM response details."""

    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None


@dataclass(frozen=True, slots=True)
class PricingSpec:
    """Confirmed pricing metadata for a model."""

    provider: str
    model: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    source: str
    checked_on: date


@dataclass(frozen=True, slots=True)
class ProviderCallContext:
    """Request settings shared by provider adapters."""

    prompt: str
    system_prompt: str | None
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class ProviderFailure(RuntimeError):
    """Safe provider failure without exposing secrets or raw SDK errors."""

    provider: str
    model: str
    error_type: str
    retryable: bool
    http_status: int | None = None
    retry_after_seconds: float | None = None
    message: str = ""

    def __str__(self) -> str:
        parts = [f"provider={self.provider}", f"model={self.model}", f"error={self.error_type}"]
        if self.http_status is not None:
            parts.append(f"http_status={self.http_status}")
        parts.append(f"retryable={self.retryable}")
        if self.message:
            parts.append(self.message)
        return " | ".join(parts)


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    """Current day budget usage."""

    day: str
    spent_usd: Decimal
    daily_budget: Decimal

    @property
    def remaining_usd(self) -> Decimal:
        """Return the remaining budget for the current day."""

        return max(Decimal("0"), self.daily_budget - self.spent_usd)


class BudgetExceededError(RuntimeError):
    """Raised when a call would exceed the remaining daily budget."""


class LLMProviderError(RuntimeError):
    """Raised when no provider can satisfy the task."""


class RateLimiter:
    """Process-local rate limiter for a single provider."""

    def __init__(
        self,
        provider: str,
        *,
        min_interval_seconds: float,
        monotonic_fn: Callable[[], float] = monotonic,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self._provider = provider
        self._min_interval_seconds = max(0.0, float(min_interval_seconds))
        self._monotonic = monotonic_fn
        self._sleep = sleep_fn
        self._last_call_time: float | None = None

    def wait(self) -> float:
        """Wait long enough to respect the configured interval."""

        if self._min_interval_seconds <= 0:
            self._last_call_time = self._monotonic()
            return 0.0

        now = self._monotonic()
        if self._last_call_time is None:
            self._last_call_time = now
            return 0.0

        elapsed = now - self._last_call_time
        if elapsed < self._min_interval_seconds:
            delay = self._min_interval_seconds - elapsed
            self._sleep(delay)
            now = self._monotonic()
        else:
            delay = 0.0
        self._last_call_time = now
        return delay


class BudgetLedger:
    """Persistent daily budget ledger stored locally on disk."""

    def __init__(self, daily_budget: Decimal, path: Path = _BUDGET_STATE_FILE) -> None:
        self._path = path
        self._daily_budget = _quantize(Decimal(str(daily_budget)))
        self._status = self._load()

    @property
    def status(self) -> BudgetStatus:
        """Return the current budget status."""

        return self._status

    def can_afford(self, estimated_cost: Decimal) -> bool:
        """Check whether an estimated call fits into the remaining budget."""

        return estimated_cost <= self._status.remaining_usd

    def record(self, amount: Decimal) -> None:
        """Atomically persist a spending update."""

        today = _today_key()
        if self._status.day != today:
            self._status = BudgetStatus(day=today, spent_usd=Decimal("0"), daily_budget=self._daily_budget)
        updated = BudgetStatus(
            day=today,
            spent_usd=_quantize(self._status.spent_usd + _quantize(amount)),
            daily_budget=self._daily_budget,
        )
        payload = {
            "day": updated.day,
            "spent_usd": str(updated.spent_usd),
            "note": _BUDGET_NOTE,
        }
        self._atomic_write(payload)
        self._status = updated

    def _load(self) -> BudgetStatus:
        """Load the current ledger state or initialize a fresh day."""

        today = _today_key()
        if not self._path.exists():
            return BudgetStatus(day=today, spent_usd=Decimal("0"), daily_budget=self._daily_budget)

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return BudgetStatus(day=today, spent_usd=Decimal("0"), daily_budget=self._daily_budget)

        if not isinstance(raw, dict) or raw.get("day") != today:
            return BudgetStatus(day=today, spent_usd=Decimal("0"), daily_budget=self._daily_budget)

        try:
            spent = Decimal(str(raw.get("spent_usd", "0")))
        except Exception:
            spent = Decimal("0")
        return BudgetStatus(day=today, spent_usd=max(Decimal("0"), spent), daily_budget=self._daily_budget)

    def _atomic_write(self, payload: Mapping[str, Any]) -> None:
        """Write the state file atomically."""

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(self._path.parent),
            prefix=f".{self._path.stem}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, self._path)


class OpenAIAdapter:
    """Adapter around the OpenAI Responses API."""

    def __init__(
        self,
        config: Config,
        *,
        client: OpenAI | None = None,
        pricing: PricingSpec | None = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAI(
            api_key=config.openai_api_key,
            timeout=config.request_timeout,
            max_retries=0,
        )
        self._pricing = pricing or PricingSpec(
            provider="openai",
            model=OPENAI_MODEL,
            input_cost_per_million=Decimal("0.15"),
            output_cost_per_million=Decimal("0.60"),
            source="OpenAI GPT-4o mini pricing page and model page",
            checked_on=date(2026, 10, 20),
        )

    @property
    def model(self) -> str:
        """Return the model name used by this adapter."""

        return self._pricing.model

    @property
    def pricing(self) -> PricingSpec:
        """Return the pricing specification."""

        return self._pricing

    def request(self, context: ProviderCallContext) -> Any:
        """Send a request to OpenAI and return the raw response object."""

        kwargs: dict[str, Any] = {
            "model": self._pricing.model,
            "input": context.prompt,
            "max_output_tokens": context.max_output_tokens,
        }
        if context.system_prompt:
            kwargs["instructions"] = context.system_prompt
        return self._client.responses.create(**kwargs)

    def extract_usage(self, response: Any) -> tuple[int | None, int | None]:
        """Extract billing usage from an OpenAI response object."""

        usage = getattr(response, "usage", None)
        if usage is None:
            return None, None
        input_tokens = _safe_int(getattr(usage, "input_tokens", None))
        output_tokens = _safe_int(getattr(usage, "output_tokens", None))
        return input_tokens, output_tokens

    def extract_text(self, response: Any) -> str:
        """Extract response text from the OpenAI SDK payload."""

        direct_text = getattr(response, "output_text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        output = getattr(response, "output", None)
        if isinstance(output, list):
            fragments: list[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if isinstance(content, list):
                    for part in content:
                        text = getattr(part, "text", None)
                        if isinstance(text, str) and text.strip():
                            fragments.append(text.strip())
            combined = "\n".join(fragment for fragment in fragments if fragment)
            if combined.strip():
                return combined.strip()
        raise ProviderFailure(
            provider=self._pricing.provider,
            model=self._pricing.model,
            error_type="empty_text",
            retryable=False,
            message="OpenAI response did not include usable text.",
        )


class CohereAdapter:
    """Adapter around the Cohere Chat API."""

    def __init__(
        self,
        config: Config,
        *,
        client: cohere.ClientV2 | None = None,
        pricing: PricingSpec | None = None,
    ) -> None:
        self._config = config
        self._client = client or cohere.ClientV2(
            api_key=config.cohere_api_key,
            timeout=config.request_timeout,
            max_retries=0,
        )
        self._pricing = pricing or PricingSpec(
            provider="cohere",
            model=COHERE_MODEL,
            input_cost_per_million=Decimal("0.0375"),
            output_cost_per_million=Decimal("0.15"),
            source="Cohere Command R7B model page and pricing page",
            checked_on=date(2026, 10, 20),
        )

    @property
    def model(self) -> str:
        """Return the model name used by this adapter."""

        return self._pricing.model

    @property
    def pricing(self) -> PricingSpec:
        """Return the pricing specification."""

        return self._pricing

    def request(self, context: ProviderCallContext) -> Any:
        """Send a request to Cohere and return the raw response object."""

        messages: list[dict[str, str]] = []
        if context.system_prompt:
            messages.append({"role": "system", "content": context.system_prompt})
        messages.append({"role": "user", "content": context.prompt})
        return self._client.chat(
            model=self._pricing.model,
            messages=messages,
            max_tokens=context.max_output_tokens,
        )

    def extract_usage(self, response: Any) -> tuple[int | None, int | None]:
        """Extract billed usage from a Cohere response object."""

        usage = getattr(response, "usage", None)
        billed_units = getattr(usage, "billed_units", None) if usage is not None else None
        if billed_units is None:
            return None, None
        input_tokens = _safe_int(getattr(billed_units, "input_tokens", None))
        output_tokens = _safe_int(getattr(billed_units, "output_tokens", None))
        return input_tokens, output_tokens

    def extract_text(self, response: Any) -> str:
        """Extract response text from the Cohere SDK payload."""

        message = getattr(response, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if isinstance(content, list):
            fragments: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                else:
                    text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    fragments.append(text.strip())
            combined = "\n".join(fragment for fragment in fragments if fragment)
            if combined.strip():
                return combined.strip()
        direct_text = getattr(response, "text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()
        raise ProviderFailure(
            provider=self._pricing.provider,
            model=self._pricing.model,
            error_type="empty_text",
            retryable=False,
            message="Cohere response did not include usable text.",
        )


class LLMService:
    """Coordinator for provider calls, retries, fallback, and budget tracking."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        openai_adapter: OpenAIAdapter | None = None,
        cohere_adapter: CohereAdapter | None = None,
        budget_ledger: BudgetLedger | None = None,
        rate_limiters: dict[str, RateLimiter] | None = None,
        sleep_fn: Callable[[float], None] = sleep,
        random_fn: Callable[[], float] = random,
        monotonic_fn: Callable[[], float] = monotonic,
        log_fn: Callable[[str], None] = print,
    ) -> None:
        self._config = config or get_config()
        self._openai = openai_adapter or OpenAIAdapter(self._config)
        self._cohere = cohere_adapter or CohereAdapter(self._config)
        self._budget = budget_ledger or BudgetLedger(Decimal(str(self._config.daily_budget)))
        self._sleep = sleep_fn
        self._random = random_fn
        self._monotonic = monotonic_fn
        self._log = log_fn
        self._rate_limiters = rate_limiters or {
            "openai": RateLimiter("openai", min_interval_seconds=_OPENAI_MIN_INTERVAL_SECONDS, monotonic_fn=monotonic_fn, sleep_fn=sleep_fn),
            "cohere": RateLimiter("cohere", min_interval_seconds=_COHERE_MIN_INTERVAL_SECONDS, monotonic_fn=monotonic_fn, sleep_fn=sleep_fn),
        }

    @property
    def budget_status(self) -> BudgetStatus:
        """Return the current persisted budget status."""

        return self._budget.status

    def ask_with_fallback(
        self,
        task: str,
        *,
        primary_provider: str = "openai",
        fallback_provider: str = "cohere",
        system_prompt: str | None = None,
        max_output_tokens: int = OUTPUT_TOKEN_LIMIT,
        result_validator: Callable[[LLMResult], None] | None = None,
        attempt_hook: Callable[[LLMResult], None] | None = None,
    ) -> LLMResult:
        """Run a task on the primary provider and fall back to the secondary provider."""

        if primary_provider == fallback_provider:
            raise ValueError("primary_provider and fallback_provider must be different")

        last_error: ProviderFailure | None = None
        for index, provider_name in enumerate((primary_provider, fallback_provider), start=1):
            adapter = self._get_adapter(provider_name)
            context = ProviderCallContext(
                prompt=task,
                system_prompt=system_prompt,
                max_output_tokens=max_output_tokens,
            )
            try:
                return self._call_provider(
                    adapter,
                    context,
                    task=task,
                    is_fallback=index > 1,
                    result_validator=result_validator,
                    attempt_hook=attempt_hook,
                )
            except BudgetExceededError:
                raise
            except ProviderFailure as exc:
                last_error = exc
                if index == 1:
                    self._log_switch(task, provider_name, adapter.model, exc)
        if last_error is None:
            raise LLMProviderError("Both providers are unavailable.")
        raise LLMProviderError(f"Both providers failed. Last error: {last_error}") from last_error

    def _call_provider(
        self,
        adapter: OpenAIAdapter | CohereAdapter,
        context: ProviderCallContext,
        *,
        task: str,
        is_fallback: bool,
        result_validator: Callable[[LLMResult], None] | None = None,
        attempt_hook: Callable[[LLMResult], None] | None = None,
    ) -> LLMResult:
        """Call one provider with retries, rate limiting, and budget checks."""

        estimated_cost = _estimate_request_cost(adapter.pricing, context.prompt, context.system_prompt, context.max_output_tokens)
        if not self._budget.can_afford(estimated_cost):
            raise BudgetExceededError("Daily budget would be exceeded by the conservative estimate.")

        last_failure: ProviderFailure | None = None
        for attempt in range(1, self._config.max_retries + 2):
            self._rate_limiters[adapter.pricing.provider].wait()
            self._log_attempt(task=task, provider=adapter.pricing.provider, model=adapter.model, attempt=attempt, fallback=is_fallback)
            try:
                response = adapter.request(context)
                input_tokens, output_tokens = adapter.extract_usage(response)
                estimated_usage_cost = _estimate_cost(adapter.pricing, input_tokens, output_tokens)
                if estimated_usage_cost is not None:
                    self._budget.record(estimated_usage_cost)
                text = adapter.extract_text(response)
                result = LLMResult(
                    text=text,
                    provider=adapter.pricing.provider,
                    model=adapter.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimated_usage_cost,
                )
                if attempt_hook is not None:
                    attempt_hook(result)
                if result_validator is not None:
                    try:
                        result_validator(result)
                    except Exception as validation_exc:
                        failure = ProviderFailure(
                            provider=adapter.pricing.provider,
                            model=adapter.model,
                            error_type=type(validation_exc).__name__,
                            retryable=False,
                            message="response validation failed",
                        )
                        self._log_failure(task=task, failure=failure, attempt=attempt, fallback=is_fallback)
                        last_failure = failure
                        break
                self._log_success(task=task, result=result, attempt=attempt, fallback=is_fallback)
                return result
            except ProviderFailure as exc:
                last_failure = exc
                self._log_failure(task=task, failure=exc, attempt=attempt, fallback=is_fallback)
                if not exc.retryable or attempt >= self._config.max_retries + 1:
                    break
                self._sleep_backoff(attempt - 1, exc)
            except Exception as exc:
                failure = _classify_exception(adapter.pricing.provider, adapter.model, exc)
                last_failure = failure
                self._log_failure(task=task, failure=failure, attempt=attempt, fallback=is_fallback)
                if not failure.retryable or attempt >= self._config.max_retries + 1:
                    break
                self._sleep_backoff(attempt - 1, failure)
        if last_failure is None:
            last_failure = ProviderFailure(
                provider=adapter.pricing.provider,
                model=adapter.model,
                error_type="unknown_failure",
                retryable=False,
                message="Unknown provider failure.",
            )
        raise last_failure

    def _get_adapter(self, provider_name: str) -> OpenAIAdapter | CohereAdapter:
        """Return the configured adapter for a provider."""

        if provider_name == "openai":
            return self._openai
        if provider_name == "cohere":
            return self._cohere
        raise ValueError(f"Unsupported provider: {provider_name}")

    def _sleep_backoff(self, attempt_index: int, failure: ProviderFailure) -> None:
        """Sleep with exponential backoff, jitter, and retry-after caps."""

        delay = min(2 ** attempt_index, 30)
        jitter = self._random() * 0.5
        retry_after = failure.retry_after_seconds
        if retry_after is not None:
            delay = min(delay + jitter, retry_after)
        else:
            delay = delay + jitter
        self._sleep(max(0.0, delay))

    def _log_attempt(self, *, task: str, provider: str, model: str, attempt: int, fallback: bool) -> None:
        """Emit a safe attempt log line."""

        phase = "fallback" if fallback else "primary"
        self._log(f"task={_safe_preview(task)} provider={provider} model={model} attempt={attempt} phase={phase}")

    def _log_failure(self, *, task: str, failure: ProviderFailure, attempt: int, fallback: bool) -> None:
        """Emit a safe failure log line."""

        phase = "fallback" if fallback else "primary"
        self._log(
            f"task={_safe_preview(task)} provider={failure.provider} model={failure.model} attempt={attempt} phase={phase} error={failure.error_type} retryable={failure.retryable}"
        )

    def _log_success(self, *, task: str, result: LLMResult, attempt: int, fallback: bool) -> None:
        """Emit a safe success log line."""

        phase = "fallback" if fallback else "primary"
        self._log(
            f"task={_safe_preview(task)} provider={result.provider} model={result.model} attempt={attempt} phase={phase} usage=input={_fmt_usage(result.input_tokens)} output={_fmt_usage(result.output_tokens)} estimated_cost_usd={_fmt_decimal(result.estimated_cost_usd)}"
        )

    def _log_switch(self, task: str, provider: str, model: str, failure: ProviderFailure) -> None:
        """Emit a safe fallback transition log line."""

        self._log(
            f"task={_safe_preview(task)} provider={provider} model={model} switching_to_fallback=true error={failure.error_type}"
        )


def ask_with_fallback(
    task: str,
    *,
    primary_provider: str = "openai",
    fallback_provider: str = "cohere",
    system_prompt: str | None = None,
    max_output_tokens: int = OUTPUT_TOKEN_LIMIT,
    result_validator: Callable[[LLMResult], None] | None = None,
    attempt_hook: Callable[[LLMResult], None] | None = None,
    service: LLMService | None = None,
    config: Config | None = None,
) -> LLMResult:
    """Ask one provider and fall back to the other if needed."""

    active_service = service or _get_default_service(config=config)
    return active_service.ask_with_fallback(
        task,
        primary_provider=primary_provider,
        fallback_provider=fallback_provider,
        system_prompt=system_prompt,
        max_output_tokens=max_output_tokens,
        result_validator=result_validator,
        attempt_hook=attempt_hook,
    )


def _get_default_service(*, config: Config | None = None) -> LLMService:
    """Return a process-local default service."""

    global _DEFAULT_SERVICE
    if _DEFAULT_SERVICE is None:
        _DEFAULT_SERVICE = LLMService(config=config)
    return _DEFAULT_SERVICE


_DEFAULT_SERVICE: LLMService | None = None


def _estimate_request_cost(
    pricing: PricingSpec,
    prompt: str,
    system_prompt: str | None,
    max_output_tokens: int,
) -> Decimal:
    """Estimate request cost conservatively before sending it."""

    input_tokens = _estimate_tokens(prompt) + _estimate_tokens(system_prompt) + 32
    return _estimate_cost(pricing, input_tokens, max_output_tokens) or Decimal("0")


def _estimate_cost(
    pricing: PricingSpec,
    input_tokens: int | None,
    output_tokens: int | None,
) -> Decimal | None:
    """Compute estimated cost from billing units or usage tokens."""

    if input_tokens is None or output_tokens is None:
        return None
    input_cost = Decimal(input_tokens) * pricing.input_cost_per_million / Decimal("1000000")
    output_cost = Decimal(output_tokens) * pricing.output_cost_per_million / Decimal("1000000")
    return _quantize(input_cost + output_cost)


def _classify_exception(provider: str, model: str, exc: Exception) -> ProviderFailure:
    """Map SDK exceptions to safe retry and error categories."""

    error_type = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    retry_after_seconds = _extract_retry_after(exc)

    non_retryable = (
        OpenAIAuthenticationError,
        OpenAIPermissionDeniedError,
        OpenAIBadRequestError,
        CohereUnauthorizedError,
        CohereForbiddenError,
        CohereBadRequestError,
        CohereUnprocessableEntityError,
    )
    retryable_types = (
        OpenAITimeoutError,
        OpenAIAPIConnectionError,
        OpenAIInternalServerError,
        OpenAIRateLimitError,
        OpenAIAPIError,
        OpenAIAPIStatusError,
        CohereGatewayTimeoutError,
        CohereInternalServerError,
        CohereServiceUnavailableError,
        CohereTooManyRequestsError,
    )
    if isinstance(exc, non_retryable):
        return ProviderFailure(
            provider=provider,
            model=model,
            error_type=error_type,
            retryable=False,
            http_status=_safe_int(status_code),
            retry_after_seconds=retry_after_seconds,
            message="non-retryable provider error",
        )
    if isinstance(exc, retryable_types):
        return ProviderFailure(
            provider=provider,
            model=model,
            error_type=error_type,
            retryable=True,
            http_status=_safe_int(status_code),
            retry_after_seconds=retry_after_seconds,
            message="retryable provider error",
        )
    if isinstance(exc, TimeoutError):
        return ProviderFailure(
            provider=provider,
            model=model,
            error_type=error_type,
            retryable=True,
            http_status=_safe_int(status_code),
            retry_after_seconds=retry_after_seconds,
            message="timeout",
        )
    return ProviderFailure(
        provider=provider,
        model=model,
        error_type=error_type,
        retryable=False,
        http_status=_safe_int(status_code),
        retry_after_seconds=retry_after_seconds,
        message="unknown provider error",
    )


def _extract_retry_after(exc: Exception) -> float | None:
    """Extract a capped Retry-After value from an SDK exception if present."""

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) if response is not None else None
    if headers is None:
        headers = getattr(exc, "headers", None)
    if not headers:
        return None
    header_value = None
    for key in ("Retry-After", "retry-after"):
        if isinstance(headers, Mapping):
            header_value = headers.get(key)
        elif hasattr(headers, "get"):
            header_value = headers.get(key)
        if header_value is not None:
            break
    if header_value is None:
        return None
    try:
        retry_after = float(header_value)
    except (TypeError, ValueError):
        return None
    if retry_after <= 0:
        return None
    return min(retry_after, 30.0)


def _estimate_tokens(text: str | None) -> int:
    """Conservatively approximate token usage without external dependencies."""

    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _safe_int(value: Any) -> int | None:
    """Convert a numeric-like value to int if possible."""

    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_preview(text: str, limit: int = 80) -> str:
    """Return a compact, safe log preview."""

    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _fmt_usage(value: int | None) -> str:
    """Format usage fields for logs."""

    return str(value) if value is not None else "unknown"


def _fmt_decimal(value: Decimal | None) -> str:
    """Format costs for logs."""

    return str(value) if value is not None else "unknown"


def _quantize(value: Decimal) -> Decimal:
    """Round monetary values to micro-dollars for stable comparisons."""

    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _today_key() -> str:
    """Return the current day in Europe/Berlin."""

    return datetime.now(_BERLIN_TZ).date().isoformat()
