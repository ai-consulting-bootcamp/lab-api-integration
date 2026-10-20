from __future__ import annotations

from pathlib import Path


def pytest_configure(config):
    """Keep pytest temporary directories inside the repository."""

    config.option.basetemp = str(Path(__file__).resolve().parent / ".pytest_tmp")
