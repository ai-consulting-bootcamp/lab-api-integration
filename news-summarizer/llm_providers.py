"""OpenAI and Cohere adapters with token and cost tracking."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from cohere import Client
from openai import OpenAI

from config import get_config


config = get_config()
OPENAI_MODEL = config.openai_model
COHERE_MODEL = config.cohere_model

openai_client = OpenAI(api_key=config.openai_api_key) if config.openai_api_key else None
# Cohere is the second provider; its key and model come from Config/.env.
cohere_client = Client(api_key=config.cohere_api_key) if config.cohere_api_key else None


@dataclass(frozen=True)
class ProviderResult:
    """Normalized provider response with usage and estimated cost."""

    provider: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

    def __getitem__(self, key: str) -> Any:
        """Support the previous dictionary-style response access."""

        if key == "response":
            return self.text
        if key == "usage":
            if self.provider == "cohere":
                return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}
            return {
                "prompt_tokens": self.input_tokens,
                "completion_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            }
        return getattr(self, key)


class CostTracker:
    """Accumulate token usage and estimated costs."""

    def __init__(self) -> None:
        self.results: list[ProviderResult] = []

    def add(self, result: ProviderResult) -> None:
        self.results.append(result)

    @property
    def total_cost_usd(self) -> float:
        return sum(result.cost_usd for result in self.results)

    def summary(self) -> str:
        lines = ["Cost summary:"]
        for result in self.results:
            lines.append(
                f"- {result.provider} ({result.model}): "
                f"{result.input_tokens} input + {result.output_tokens} output tokens "
                f"= ${result.cost_usd:.6f}"
            )
        lines.append(f"Total estimated cost: ${self.total_cost_usd:.6f}")
        return "\n".join(lines)


def _cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost using configurable per-million-token rates."""

    defaults = {"openai": (0.15, 0.60), "cohere": (0.50, 1.50)}
    input_default, output_default = defaults[provider]
    input_rate = float(os.getenv(f"{provider.upper()}_INPUT_COST_PER_MILLION", input_default))
    output_rate = float(os.getenv(f"{provider.upper()}_OUTPUT_COST_PER_MILLION", output_default))
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def ask_openai(prompt: str, model: str = OPENAI_MODEL) -> ProviderResult:
    """Ask OpenAI and return response, usage, and estimated cost."""

    if openai_client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
    )
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    return ProviderResult(
        "openai", model, response.choices[0].message.content or "",
        input_tokens, output_tokens, _cost("openai", input_tokens, output_tokens)
    )


def ask_cohere(prompt: str, model: str = COHERE_MODEL) -> ProviderResult:
    """Ask Cohere and return response, usage, and estimated cost."""

    if cohere_client is None:
        raise RuntimeError("COHERE_API_KEY is not configured.")
    response = cohere_client.chat(model=model, message=prompt)
    tokens = getattr(getattr(response, "meta", None), "tokens", None)
    input_tokens = getattr(tokens, "input_tokens", 0) if tokens else 0
    output_tokens = getattr(tokens, "output_tokens", 0) if tokens else 0
    return ProviderResult(
        "cohere", model, getattr(response, "text", "") or "",
        input_tokens, output_tokens, _cost("cohere", input_tokens, output_tokens)
    )


def test_providers(prompt: str) -> CostTracker:
    """Call OpenAI and Cohere, display their responses, and show total cost."""

    tracker = CostTracker()
    for name, api_key, ask in (
        ("OpenAI", config.openai_api_key, ask_openai),
        ("Cohere", config.cohere_api_key, ask_cohere),
    ):
        if not api_key:
            print(f"{name}: skipped because its API key is not configured.")
            continue
        try:
            result = ask(prompt)
            tracker.add(result)
            print(f"\n{name} response:\n{result.text}")
            print(
                f"Usage: {result.input_tokens} input + {result.output_tokens} output; "
                f"estimated cost: ${result.cost_usd:.6f}"
            )
        except Exception as exc:  # SDK exception types differ between providers.
            print(f"{name}: request failed ({exc})")
    print(f"\n{tracker.summary()}")
    return tracker


if __name__ == "__main__":
    test_providers("In one sentence, explain why API integration needs error handling.")
