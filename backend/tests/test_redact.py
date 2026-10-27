import pytest
from app.core.config import settings
from app.core.security import redact
from app.core.db import SessionLocal
from app.models.user import User
from app.models.deck import Deck
from app.models.job import Job
from app.llm.base import LLMClient
from app.llm.gemini import GeminiServiceError
from app.services.events import JobEventPublisher
from app.services.generator import run_card_generation, run_vision_card_generation


def test_redact_url_with_key_query_param() -> None:
    raw_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AQ.FakeDummyKeyForTestingRedaction1234567890abcdef"
    redacted = redact(raw_url)
    assert "AQ.FakeDummyKeyForTestingRedaction1234567890abcdef" not in redacted
    assert "key=[REDACTED]" in redacted


def test_redact_url_with_ampersand_key() -> None:
    raw_url = "https://example.com/api?param=1&key=AIzaSyD-1234567890abcdefghijklmnopqrstuvwx&other=2"
    redacted = redact(raw_url)
    assert "AIzaSyD-1234567890abcdefghijklmnopqrstuvwx" not in redacted
    assert "&key=[REDACTED]" in redacted


def test_redact_authorization_header() -> None:
    header = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.sig"
    redacted = redact(header)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "Authorization: [REDACTED]" in redacted


def test_redact_x_goog_api_key_header() -> None:
    header = "x-goog-api-key: AQ.FakeDummyKeyForTestingRedaction1234567890abcdef"
    redacted = redact(header)
    assert "AQ.FakeDummyKeyForTestingRedaction1234567890abcdef" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_bare_keys() -> None:
    sample_text = (
        "Client error for key AQ.FakeDummyKeyForTestingRedaction1234567890abcdef "
        "and also AIzaSyB1234567890abcdefghijklmnopqrstuv"
    )
    redacted = redact(sample_text)
    assert "AQ.FakeDummyKeyForTestingRedaction1234567890abcdef" not in redacted
    assert "AIzaSyB1234567890abcdefghijklmnopqrstuv" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_configured_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_key = "super-secret-gemini-key-12345"
    jwt_secret = "super-secret-jwt-token-signing-key-999"
    monkeypatch.setattr(settings, "GEMINI_API_KEY", secret_key)
    monkeypatch.setattr(settings, "JWT_SECRET", jwt_secret)

    sample_err = f"Failed to authenticate with {secret_key} and token signed by {jwt_secret}"
    redacted = redact(sample_err)
    assert secret_key not in redacted
    assert jwt_secret not in redacted
    assert "[REDACTED]" in redacted


class Mock404LLMClient(LLMClient):
    """Mock LLM client that raises 404 model unavailable."""
    def generate_cards(self, chunk_text: str):
        raise GeminiServiceError(
            status_code=404,
            user_message="The AI service is temporarily unavailable. Please try again later.",
            model_name="gemini-old-model",
            server_log="GEMINI_MODEL is unavailable, update the env var (model: gemini-old-model, status: 404)",
        )

    def generate_cards_from_pdf(self, pdf_bytes: bytes, page_range_label: str):
        raise GeminiServiceError(
            status_code=404,
            user_message="The AI service is temporarily unavailable. Please try again later.",
            model_name="gemini-old-model",
            server_log="GEMINI_MODEL is unavailable, update the env var (model: gemini-old-model, status: 404)",
        )


class MockEventPublisher(JobEventPublisher):
    def __init__(self):
        self.failed_messages = []

    def chunk_done(self, job_id, chunk_index, total_chunks, new_cards, cards_created, page_range=""):
        pass

    def chunk_failed(self, job_id, chunk_index, reason):
        pass

    def ready(self, job_id, deck_id, cards_created):
        pass

    def failed(self, job_id, message):
        self.failed_messages.append(message)


def test_job_generation_404_sets_generic_user_message_and_no_secret(db_session) -> None:
    """When a 404 occurs during generation, the job fails with the user-safe message and no leaked URL/key."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    user = User(email=f"user_{uid}@example.com", password_hash="dummy", display_name="Test 404")
    db_session.add(user)
    db_session.flush()

    deck = Deck(user_id=user.id, title="Test 404 Deck", source_filename="notes.pdf", file_hash=f"hash_404_{uid}")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user.id, deck_id=deck.id, status="queued")
    db_session.add(job)
    db_session.commit()
    job_id = job.id
    user_id = user.id
    deck_id = deck.id

    publisher = MockEventPublisher()
    mock_llm = Mock404LLMClient()

    # Run generation
    run_card_generation(
        job_id=job_id,
        user_id=user_id,
        deck_id=deck_id,
        chunks=["Chunk 1", "Chunk 2"],
        llm_client=mock_llm,
        publisher=publisher,
        delay_between_chunks=0,
    )

    db_session.expire_all()
    updated_job = db_session.get(Job, job_id)
    assert updated_job.status == "failed"
    # Generic user message
    assert updated_job.error_message == "The AI service is temporarily unavailable. Please try again later."
    # No secret, no URL, no key
    assert "key=" not in updated_job.error_message
    assert "AQ." not in updated_job.error_message
    assert "AIza" not in updated_job.error_message
    assert publisher.failed_messages == ["The AI service is temporarily unavailable. Please try again later."]


def test_vision_generation_404_sets_generic_user_message(db_session) -> None:
    """When a 404 occurs during vision generation, the job fails with user-safe message and no secret."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    user = User(email=f"user_vis_{uid}@example.com", password_hash="dummy", display_name="Test Vision 404")
    db_session.add(user)
    db_session.flush()

    deck = Deck(user_id=user.id, title="Test Vision 404 Deck", source_filename="scanned.pdf", file_hash=f"hash_vis_{uid}")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user.id, deck_id=deck.id, status="queued", is_vision=True)
    db_session.add(job)
    db_session.commit()
    job_id = job.id
    user_id = user.id
    deck_id = deck.id

    publisher = MockEventPublisher()
    mock_llm = Mock404LLMClient()

    run_vision_card_generation(
        job_id=job_id,
        user_id=user_id,
        deck_id=deck_id,
        chunks=[(b"%PDF dummy", "Pages 1-4")],
        llm_client=mock_llm,
        publisher=publisher,
        delay_between_chunks=0,
    )

    db_session.expire_all()
    updated_job = db_session.get(Job, job_id)
    assert updated_job.status == "failed"
    assert updated_job.error_message == "The AI service is temporarily unavailable. Please try again later."
    assert "key=" not in updated_job.error_message
    assert publisher.failed_messages == ["The AI service is temporarily unavailable. Please try again later."]


@pytest.mark.anyio
async def test_startup_production_model_check_warning_on_404(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    """In production with GEMINI_API_KEY set, startup logs a warning if model returns 404, but does not block."""
    import httpx
    import logging
    from app.main import lifespan, app

    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.test_key_1234567890abcdef")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-nonexistent")

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert "key=" not in str(request.url)
        assert request.headers.get("x-goog-api-key") == "AQ.test_key_1234567890abcdef"
        assert "models/gemini-nonexistent" in str(request.url)
        return httpx.Response(404, json={"error": "Not Found"})

    transport = httpx.MockTransport(mock_handler)

    orig_client = httpx.AsyncClient

    def mock_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr("app.main.httpx.AsyncClient", mock_async_client)

    with caplog.at_level(logging.WARNING):
        async with lifespan(app):
            pass

    # Verify warning logged
    assert any("Configured GEMINI_MODEL 'gemini-nonexistent' was not found" in record.message for record in caplog.records)
    # Verify key is never in logs
    assert not any("AQ.test_key_1234567890abcdef" in record.message for record in caplog.records)


