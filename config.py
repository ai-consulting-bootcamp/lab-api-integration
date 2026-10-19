"""Configuration loading and validation for the news summarizer."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from os import environ as os_environ
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

_DEFAULT_ENVIRONMENT = "development"
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_REQUEST_TIMEOUT = 30
_DEFAULT_DAILY_BUDGET = 5.00

_ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}


class ConfigError(ValueError):
    """Raised when configuration values are missing or invalid."""


@dataclass(frozen=True, slots=True, repr=False)
class Config:
    """Validated runtime configuration."""

    openai_api_key: str
    cohere_api_key: str
    news_api_key: str
    environment: str
    max_retries: int
    request_timeout: float
    daily_budget: float

    def __repr__(self) -> str:
        """Return a safe representation without secret values."""

        return (
            "Config("
            f"environment={self.environment!r}, "
            f"max_retries={self.max_retries!r}, "
            f"request_timeout={self.request_timeout!r}, "
            f"daily_budget={self.daily_budget!r})"
        )


@dataclass(frozen=True, slots=True)
class ConfigReport:
    """Safe configuration summary for command-line output."""

    environment: str
    max_retries: int | None
    request_timeout: float | None
    daily_budget: float | None
    openai_status: str
    cohere_status: str
    news_status: str


def get_config(
    *,
    environ: Mapping[str, str] | None = None,
    load_dotenv_file: bool = True,
) -> Config:
    """Load and validate runtime configuration.

    Parameters
    ----------
    environ:
        Optional mapping of environment variables used instead of ``os.environ``.
    load_dotenv_file:
        When ``True``, load ``.env`` relative to this file before reading values.
    """

    values = _effective_values(environ=environ, load_dotenv_file=load_dotenv_file)
    return _build_config(values)


def build_report(
    *,
    environ: Mapping[str, str] | None = None,
    load_dotenv_file: bool = True,
) -> ConfigReport:
    """Build a safe, non-secret configuration report."""

    values = _effective_values(environ=environ, load_dotenv_file=load_dotenv_file)
    environment = _normalize_text(
        values.get("ENVIRONMENT"),
        default=_DEFAULT_ENVIRONMENT,
        allow_placeholder=False,
    )

    max_retries = _parse_int(values.get("MAX_RETRIES"), default=_DEFAULT_MAX_RETRIES)
    request_timeout = _parse_positive_float(
        values.get("REQUEST_TIMEOUT"), default=_DEFAULT_REQUEST_TIMEOUT
    )
    daily_budget = _parse_positive_float(values.get("DAILY_BUDGET"), default=_DEFAULT_DAILY_BUDGET)

    return ConfigReport(
        environment=environment if environment is not None else _DEFAULT_ENVIRONMENT,
        max_retries=max_retries,
        request_timeout=request_timeout,
        daily_budget=daily_budget,
        openai_status=_secret_status(values.get("OPENAI_API_KEY")),
        cohere_status=_secret_status(values.get("COHERE_API_KEY")),
        news_status=_secret_status(values.get("NEWS_API_KEY")),
    )


def _effective_values(
    *,
    environ: Mapping[str, str] | None,
    load_dotenv_file: bool,
) -> dict[str, str]:
    """Return effective configuration values without mutating caller state."""

    if load_dotenv_file and environ is None:
        load_dotenv(dotenv_path=_dotenv_path(), override=False)

    source = os_environ if environ is None else environ
    keys = {
        "OPENAI_API_KEY",
        "COHERE_API_KEY",
        "NEWS_API_KEY",
        "ENVIRONMENT",
        "MAX_RETRIES",
        "REQUEST_TIMEOUT",
        "DAILY_BUDGET",
    }
    return {key: source[key] for key in keys if key in source}


def _build_config(values: Mapping[str, str]) -> Config:
    """Validate effective values and construct ``Config``."""

    missing = [
        name
        for name in ("OPENAI_API_KEY", "COHERE_API_KEY", "NEWS_API_KEY")
        if name not in values
    ]
    if missing:
        raise ConfigError(f"Missing required configuration values: {', '.join(missing)}")

    openai_api_key = _normalize_text(values.get("OPENAI_API_KEY"), allow_placeholder=False)
    cohere_api_key = _normalize_text(values.get("COHERE_API_KEY"), allow_placeholder=False)
    news_api_key = _normalize_text(values.get("NEWS_API_KEY"), allow_placeholder=False)

    invalid_secret_names = [
        name
        for name, value in (
            ("OPENAI_API_KEY", values.get("OPENAI_API_KEY")),
            ("COHERE_API_KEY", values.get("COHERE_API_KEY")),
            ("NEWS_API_KEY", values.get("NEWS_API_KEY")),
        )
        if _is_invalid_secret(value)
    ]

    environment = _normalize_text(
        values.get("ENVIRONMENT"),
        default=_DEFAULT_ENVIRONMENT,
        allow_placeholder=False,
    )
    if environment is None or environment not in _ALLOWED_ENVIRONMENTS:
        raise ConfigError("Invalid configuration value: ENVIRONMENT must be development, staging, or production")

    max_retries = _parse_int(values.get("MAX_RETRIES"), default=_DEFAULT_MAX_RETRIES)
    if max_retries is None or max_retries < 0:
        raise ConfigError("Invalid configuration value: MAX_RETRIES must be an integer greater than or equal to 0")

    request_timeout = _parse_positive_float(values.get("REQUEST_TIMEOUT"), default=_DEFAULT_REQUEST_TIMEOUT)
    if request_timeout is None:
        raise ConfigError("Invalid configuration value: REQUEST_TIMEOUT must be a positive finite number")

    daily_budget = _parse_positive_float(values.get("DAILY_BUDGET"), default=_DEFAULT_DAILY_BUDGET)
    if daily_budget is None:
        raise ConfigError("Invalid configuration value: DAILY_BUDGET must be a positive finite number")

    invalid_names = invalid_secret_names
    if invalid_names:
        raise ConfigError(
            "Invalid configuration values: " + ", ".join(sorted(set(invalid_names)))
        )

    return Config(
        openai_api_key=openai_api_key,
        cohere_api_key=cohere_api_key,
        news_api_key=news_api_key,
        environment=environment,
        max_retries=max_retries,
        request_timeout=request_timeout,
        daily_budget=daily_budget,
    )


def _normalize_text(
    value: str | None,
    *,
    default: str | None = None,
    allow_placeholder: bool,
) -> str | None:
    """Strip a string and optionally reject placeholder text."""

    if value is None:
        return default

    text = value.strip()
    if not text:
        return None
    if not allow_placeholder and _looks_like_placeholder(text):
        return None
    return text


def _parse_int(value: str | None, *, default: int | None) -> int | None:
    """Parse an integer without exposing the original value."""

    text = _normalize_text(value, default=None, allow_placeholder=False)
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return None


def _parse_positive_float(value: str | None, *, default: float | None) -> float | None:
    """Parse a positive finite number without exposing the original value."""

    text = _normalize_text(value, default=None, allow_placeholder=False)
    if text is None:
        return default
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _secret_status(value: str | None) -> str:
    """Return a safe presence status for secret values."""

    if value is None:
        return "missing"
    if _is_invalid_secret(value):
        return "invalid"
    return "present"


def _is_invalid_secret(value: str | None) -> bool:
    """Detect blank or obvious placeholder secret values."""

    if value is None:
        return True
    text = value.strip()
    if not text:
        return True
    return _looks_like_placeholder(text)


def _looks_like_placeholder(text: str) -> bool:
    """Detect common placeholder values without revealing them."""

    lowered = text.casefold()
    placeholder_markers = (
        "<",
        ">",
        "your ",
        "your-",
        "replace",
        "example",
        "changeme",
        "change-me",
        "dummy",
        "sample",
        "todo",
        "insert",
    )
    return any(marker in lowered for marker in placeholder_markers)


def _dotenv_path() -> Path:
    """Return the repository-local .env path."""

    return Path(__file__).resolve().with_name(".env")


def _print_report(report: ConfigReport) -> None:
    """Print a safe command-line report."""

    print(f"environment: {report.environment}")
    print(f"max_retries: {report.max_retries if report.max_retries is not None else 'invalid'}")
    print(
        "request_timeout: "
        f"{report.request_timeout if report.request_timeout is not None else 'invalid'}"
    )
    print(f"daily_budget: {report.daily_budget if report.daily_budget is not None else 'invalid'}")
    print(f"OPENAI_API_KEY: {report.openai_status}")
    print(f"COHERE_API_KEY: {report.cohere_status}")
    print(f"NEWS_API_KEY: {report.news_status}")


if __name__ == "__main__":
    report = build_report()
    _print_report(report)
    try:
        get_config()
    except ConfigError as exc:
        raise SystemExit(1) from exc
