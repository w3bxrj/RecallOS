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
        # Check that key is NEVER in URL
        assert "key=" not in str(request.url)
        assert request.headers.get("x-goog-api-key") == "fake-key"
        assert "models/gemini-2.5-flash:generateContent" in str(request.url)
        body = json.loads(request.content)
        prompt_text = body["contents"][0]["parts"][0]["text"]
        # Verify untrusted delimiters are present
        assert "<<<STUDY_MATERIAL_START>>>" in prompt_text
        assert "<<<STUDY_MATERIAL_END>>>" in prompt_text
        return httpx.Response(200, json=mock_response_json)

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", model_name="gemini-2.5-flash", http_client=client)

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


def test_gemini_vision_client_success() -> None:
    """Test vision card generation sends inline_data with application/pdf and parses cards."""
    import base64

    fake_pdf_bytes = b"%PDF-1.4 fake pdf binary content"
    sample_cards = [
        {
            "topic": "Mathematics",
            "question": "What is the proof that sqrt(2) is irrational?",
            "answer": "Assume sqrt(2) = p/q in lowest terms, then 2q^2 = p^2 which contradicts coprimality.",
            "distractors": [
                "Assume sqrt(2) is transcendental.",
                "Calculate pi decimals up to 10 places.",
                "Integrate 1/x from 1 to 2.",
            ],
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
        assert "key=" not in str(request.url)
        assert request.headers.get("x-goog-api-key") == "fake-key"
        assert ":generateContent" in str(request.url)
        body = json.loads(request.content)
        parts = body["contents"][0]["parts"]
        # Verify inline_data structure
        assert len(parts) == 2
        inline_part = parts[0]
        assert "inline_data" in inline_part
        assert inline_part["inline_data"]["mime_type"] == "application/pdf"
        assert inline_part["inline_data"]["data"] == base64.b64encode(fake_pdf_bytes).decode("utf-8")

        prompt_text = parts[1]["text"]
        # Verify prompt guidelines and prompt injection guard
        assert "Pages 1-4" in prompt_text
        assert "SECURITY AND INTEGRITY DIRECTIVE" in prompt_text
        assert "NOT LaTeX" in prompt_text
        return httpx.Response(200, json=mock_response_json)

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client)

    cards = gemini.generate_cards_from_pdf(fake_pdf_bytes, "Pages 1-4")
    assert len(cards) == 1
    assert cards[0]["topic"] == "Mathematics"
    assert "sqrt(2)" in cards[0]["question"]


def test_gemini_vision_client_empty_study_content_returns_empty_list() -> None:
    """When a scanned page chunk has no study content, returning empty list [] is not an error."""
    mock_response_json = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "[]"}]
                }
            }
        ]
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mock_response_json)

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client)

    cards = gemini.generate_cards_from_pdf(b"%PDF-1.4 dummy", "Pages 1-4")
    assert cards == []


def test_gemini_client_404_fails_fast_without_retrying() -> None:
    """HTTP 404 indicates the model is unavailable; must fail fast without retrying."""
    from app.llm.gemini import GeminiServiceError

    calls = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert "key=" not in str(request.url)
        assert request.headers.get("x-goog-api-key") == "fake-key"
        return httpx.Response(404, json={"error": {"message": "models/gemini-old is not found"}})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client, max_retries=2)

    with pytest.raises(GeminiServiceError) as exc_info:
        gemini.generate_cards("Notes")

    # Assert exactly 1 call (no retries!)
    assert calls == 1
    assert exc_info.value.status_code == 404
    assert exc_info.value.user_message == "The AI service is temporarily unavailable. Please try again later."


def test_gemini_client_401_403_fails_fast_without_retrying() -> None:
    """HTTP 401/403 indicates invalid API key/permissions; must fail fast without retrying."""
    from app.llm.gemini import GeminiServiceError

    calls = 0

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert "key=" not in str(request.url)
        assert request.headers.get("x-goog-api-key") == "fake-key"
        return httpx.Response(403, json={"error": {"message": "API key not valid"}})

    transport = httpx.MockTransport(mock_handler)
    client = httpx.Client(transport=transport)
    gemini = GeminiLLMClient(api_key="fake-key", http_client=client, max_retries=2)

    with pytest.raises(GeminiServiceError) as exc_info:
        gemini.generate_cards("Notes")

    # Assert exactly 1 call (no retries!)
    assert calls == 1
    assert exc_info.value.status_code == 403
    assert exc_info.value.user_message == "AI service configuration problem"

