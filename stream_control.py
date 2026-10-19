"""Collect streamed LLM text under a reserved cost ceiling."""

from dataclasses import dataclass
from decimal import Decimal

import tiktoken

from budget import DailyBudget


@dataclass
class StreamResult:
    """Completed text and provider usage, when the provider supplies it."""

    text: str
    usage: object | None


def _output_tokens(text: str) -> int:
    """Conservatively estimate output tokens from text received so far."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text)) + 8


def _check(
    budget: DailyBudget,
    reservation_id: str,
    text: str,
    input_tokens_estimate: int,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
) -> None:
    estimated = (
        Decimal(input_tokens_estimate) * input_price_per_million
        + Decimal(_output_tokens(text)) * output_price_per_million
    ) / Decimal(1_000_000)
    budget.check_stream_cost(reservation_id, estimated)


def collect_openai_stream(
    stream,
    budget: DailyBudget,
    reservation_id: str,
    input_tokens_estimate: int,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
) -> StreamResult:
    """Collect OpenAI deltas; close the stream if its budget is exceeded."""
    parts = []
    usage = None

    try:
        for chunk in stream:
            if chunk.usage is not None:
                usage = chunk.usage

            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    parts.append(delta)
                    _check(
                        budget,
                        reservation_id,
                        "".join(parts),
                        input_tokens_estimate,
                        input_price_per_million,
                        output_price_per_million,
                    )
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()

    return StreamResult("".join(parts).strip(), usage)


def collect_cohere_stream(
    stream,
    budget: DailyBudget,
    reservation_id: str,
    input_tokens_estimate: int,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
) -> StreamResult:
    """Collect Cohere deltas; close the stream if its budget is exceeded."""
    parts = []
    usage = None

    try:
        for event in stream:
            if event.type == "content-delta":
                delta = event.delta.message.content.text
                if delta:
                    parts.append(delta)
                    _check(
                        budget,
                        reservation_id,
                        "".join(parts),
                        input_tokens_estimate,
                        input_price_per_million,
                        output_price_per_million,
                    )
            elif event.type == "message-end":
                usage = event.delta.usage
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()

    return StreamResult("".join(parts).strip(), usage)