"""Persistent, local rolling-window limit for LLM requests."""

import sqlite3
import time
from pathlib import Path


class LocalRateLimitError(RuntimeError):
    """Raised when this application's request limit is reached."""


class RateLimiter:
    """Allow at most `limit` requests in any rolling 60-second window."""

    def __init__(self, limit: int, database: Path) -> None:
        if limit < 1:
            raise ValueError("Rate limit must be positive.")

        self.limit = limit
        self.database = database

        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS requests "
                "(id INTEGER PRIMARY KEY, requested_at REAL NOT NULL)"
            )

    def acquire(self) -> None:
        """Record one request slot, or reject it before the API call."""
        now = time.time()

        with sqlite3.connect(self.database, timeout=5) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM requests WHERE requested_at <= ?",
                (now - 60,),
            )
            count = connection.execute(
                "SELECT COUNT(*) FROM requests"
            ).fetchone()[0]

            if count >= self.limit:
                raise LocalRateLimitError(
                    f"Local limit of {self.limit} LLM requests per "
                    "rolling minute reached. Try again shortly."
                )

            connection.execute(
                "INSERT INTO requests (requested_at) VALUES (?)",
                (now,),
            )


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        limiter = RateLimiter(
            limit=2,
            database=Path(directory) / "test-rate-limit.sqlite3",
        )
        limiter.acquire()
        limiter.acquire()
        try:
            limiter.acquire()
        except LocalRateLimitError as error:
            print(f"Expected rejection: {error}")