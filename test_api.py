import os

import pytest
import requests


pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_API_SMOKE"),
    reason="set RUN_API_SMOKE=1 to call the running local API",
)


def test_summarise_endpoint():
    """Smoke-test the local FastAPI endpoint when the server is running."""
    response = requests.post(
        "http://127.0.0.1:8000/summarise",
        json={"text": "Artificial intelligence is transforming industries...", "max_words": 20},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    assert payload["summary"]
    assert payload["word_count"] == len(payload["summary"].split())


if __name__ == "__main__":
    test_summarise_endpoint()
