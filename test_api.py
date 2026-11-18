from unittest.mock import patch

def test_something():
    with patch("llm_providers.some_function") as fake:
        fake.return_value = "pretend response"
        result = code_under_test()
        assert result == "expected"