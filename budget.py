"""Persistent daily budget reservations for LLM requests."""

import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_UP
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

NANODOLLARS_PER_DOLLAR = Decimal("1000000000")
TIMEZONE = ZoneInfo("Europe/Berlin")


class BudgetExceededError(RuntimeError):
    """Raised before an LLM request when its reservation cannot fit."""


def to_nanodollars(amount_usd: Decimal | str | float) -> int:
    """Round a USD amount upward to an integer nanodollar."""
    amount = Decimal(str(amount_usd))
    if amount < 0:
        raise ValueError("Cost cannot be negative.")
    return int(
        (amount * NANODOLLARS_PER_DOLLAR).to_integral_value(
            rounding=ROUND_UP
        )
    )


class DailyBudget:
    """Reserve and settle estimated costs across app restarts."""

    def __init__(self, limit_usd: str, database: Path) -> None:
        self.limit_nano = to_nanodollars(limit_usd)
        if self.limit_nano < 1:
            raise ValueError("Daily budget must be positive.")

        self.database = database
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS charges (
                    id TEXT PRIMARY KEY,
                    day TEXT NOT NULL,
                    reserved_nano INTEGER NOT NULL,
                    actual_nano INTEGER
                )
                """
            )

    @staticmethod
    def _today() -> str:
        return datetime.now(TIMEZONE).date().isoformat()

    def reserve(self, maximum_usd: Decimal | str | float) -> str:
        """Reserve a request's estimated maximum cost atomically."""
        amount = to_nanodollars(maximum_usd)
        day = self._today()
        reservation_id = uuid4().hex

        with sqlite3.connect(self.database, timeout=5) as connection:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute(
                """
                SELECT COALESCE(
                    SUM(COALESCE(actual_nano, reserved_nano)), 0
                )
                FROM charges WHERE day = ?
                """,
                (day,),
            ).fetchone()[0]

            if used + amount > self.limit_nano:
                raise BudgetExceededError(
                    "Daily LLM budget would be exceeded. "
                    "No new LLM request was sent."
                )

            connection.execute(
                """
                INSERT INTO charges
                    (id, day, reserved_nano, actual_nano)
                VALUES (?, ?, ?, NULL)
                """,
                (reservation_id, day, amount),
            )

        return reservation_id

    def settle(
        self,
        reservation_id: str,
        estimated_actual_usd: Decimal | str | float,
    ) -> None:
        """Replace a reservation with estimated cost already incurred."""
        amount = to_nanodollars(estimated_actual_usd)
        with sqlite3.connect(self.database) as connection:
            cursor = connection.execute(
                """
                UPDATE charges SET actual_nano = ?
                WHERE id = ? AND actual_nano IS NULL
                """,
                (amount, reservation_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Unknown or already settled reservation.")

    def remaining_usd(self) -> Decimal:
        """Return today's available budget after charges and reservations."""
        with sqlite3.connect(self.database) as connection:
            used = connection.execute(
                """
                SELECT COALESCE(
                    SUM(COALESCE(actual_nano, reserved_nano)), 0
                )
                FROM charges WHERE day = ?
                """,
                (self._today(),),
            ).fetchone()[0]

        remaining = max(0, self.limit_nano - used)
        return Decimal(remaining) / NANODOLLARS_PER_DOLLAR

    def check_stream_cost(
        self,
        reservation_id: str,
        estimated_so_far_usd: Decimal | str | float,
    ) -> None:
        """Reject a stream once its estimated cost exceeds its reservation."""
        estimated_nano = to_nanodollars(estimated_so_far_usd)

        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                """
                SELECT reserved_nano FROM charges
                WHERE id = ? AND actual_nano IS NULL
                """,
                (reservation_id,),
            ).fetchone()

        if row is None:
            raise ValueError("Unknown or already settled reservation.")

        if estimated_nano > row[0]:
            raise BudgetExceededError(
                "Streaming cost reached the reserved budget. "
                "The partial output must be discarded."
            )