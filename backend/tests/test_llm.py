import json
import httpx
import pytest
from app.llm.base import LLMClient
from app.llm.gemini import GeminiLLMClient


def test_gemini_client_success() -> None:
    """Test successful card generation parsing JSON response."""
    sample_cards = [
        {
            "topic": "Operating Systems",
            "question": "What is thrashing?",
            "answer": "Excessive swapping where OS spends more time paging than executing.",
            "distractors": ["CPU overheating", "Network packet loss", "Deadlock detection"],
        }
    ]
    mock_response_json = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(sample_cards)}]
                }
            }
        ]
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "models/gemini-1.5-flash:generateContent" in str(request.url)
        body = json.loads(request.content)
        prompt_text = body["contents"][0]["parts"][0]["text"]
        # Verify untrusted delimiters are present
        assert "<<<STUDY_MATERIAL_START>>>" in prompt_text
        assert "<<<STUDY_MATERIAL_END>>>" in prompt_text
        return httpx.Response(200, json=mock_response_json)

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", model_name="gemini-1.5-flash", http_client=client)

    cards = gemini.generate_cards("Sample notes about operating systems.")
    assert len(cards) == 1
    assert cards[0]["question"] == "What is thrashing?"
    assert len(cards[0]["distractors"]) == 3


def test_gemini_client_retries_on_429() -> None:
    """Test that HTTP 429 triggers retry and succeeds on subsequent attempt."""
    attempt = 0
    sample_cards = [
        {"topic": "OS", "question": "Q1", "answer": "A1", "distractors": ["d1", "d2", "d3"]}
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            return httpx.Response(429, headers={"retry-after": "0.01"}, json={"error": "Rate limit"})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(sample_cards)}]}}]})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client, retry_backoff_base=0.01)

    cards = gemini.generate_cards("Notes text")
    assert attempt == 2
    assert len(cards) == 1


def test_gemini_client_invalid_json_skips_after_retries() -> None:
    """When LLM repeatedly returns invalid JSON, retries 2 times then returns empty list."""
    attempt = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt
        attempt += 1
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Not valid JSON {"}]}}]})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client, retry_backoff_base=0.01)

    cards = gemini.generate_cards("Notes text")
    # 1 initial + 2 retries = 3 attempts
    assert attempt == 3
    assert cards == []
