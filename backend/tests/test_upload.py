import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select
from pypdf import PdfWriter

from app.models.user import User
from app.models.job import Job
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_state import CardState
from app.llm.base import LLMClient


def create_user_and_token(client: TestClient, email: str) -> tuple[int, str]:
    """Helper to register and login a user."""
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": "Test User"},
    )
    user_id = reg.json()["id"]

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = login.json()["access_token"]
    return user_id, token


def create_sample_pdf_bytes(text_pages: list[str]) -> bytes:
    """Helper creating a PDF with multiple text pages or blank pages."""
    writer = PdfWriter()
    for page_text in text_pages:
        # Note: PdfWriter can add blank pages, but for text tests we can test blank / short text
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class MockLLMSuccess(LLMClient):
    """Mock LLM returning valid cards."""
    def generate_cards(self, chunk_text: str) -> list[dict]:
        return [
            {
                "topic": "Operating Systems",
                "question": "What is virtual memory?",
                "answer": "A memory management capability that provides an idealized abstraction of the storage resources.",
                "distractors": [
                    "A physical RAM chip on the motherboard.",
                    "A cache located inside the CPU registers.",
                    "A persistent storage disk formatted with FAT32."
                ]
            }
        ]


class MockLLMEmpty(LLMClient):
    """Mock LLM returning empty cards."""
    def generate_cards(self, chunk_text: str) -> list[dict]:
        return []


def test_reject_unsupported_file_extension(client: TestClient) -> None:
    """Uploading files other than PDF or TXT returns 400 UNSUPPORTED_FILE_TYPE."""
    _, token = create_user_and_token(client, "unsupported@example.com")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("photo.png", b"\x89PNG\r\n\x1a\nfakecontent", "image/png")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_reject_corrupt_pdf(client: TestClient) -> None:
    """Uploading a file with .pdf extension but invalid header returns 400 CORRUPT_PDF."""
    _, token = create_user_and_token(client, "corrupt@example.com")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("corrupt.pdf", b"not-a-pdf-content", "application/pdf")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] in ("CORRUPT_PDF", "INVALID_FILE_TYPE")


def test_reject_empty_file(client: TestClient) -> None:
    """Uploading an empty file returns 400 EMPTY_FILE."""
    _, token = create_user_and_token(client, "empty@example.com")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "EMPTY_FILE"


def test_upload_scanned_pdf_fails_job(client: TestClient) -> None:
    """A PDF with under 200 characters of extractable text fails the job with the exact message."""
    _, token = create_user_and_token(client, "scanned@example.com")
    blank_pdf = create_sample_pdf_bytes([""])

    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scanned_doc.pdf", blank_pdf, "application/pdf")},
    )
    assert res.status_code == 200
    data = res.json()
    job_id = data["job_id"]

    # Poll job status
    job_res = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "failed"
    assert "This looks like a scanned PDF. Please upload a text-based PDF." in job_data["error_message"]


def test_upload_success_and_poll_job(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploading a valid text file processes chunks, creates cards and card_states, and finishes ready."""
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMSuccess())
    _, token = create_user_and_token(client, "success@example.com")

    content = ("Operating systems provide process management, memory isolation, and file systems.\n\n" * 10).encode("utf-8")
    assert len(content) > 200

    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "OS Lecture 1"},
        files={"file": ("lecture1.txt", content, "text/plain")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "deck_id" in data
    assert "job_id" in data
    deck_id = data["deck_id"]
    job_id = data["job_id"]

    # Check job status
    job_res = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"})
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "ready"
    assert job_data["cards_created"] >= 1

    # Check cards created in deck
    cards_res = client.get(f"/api/decks/{deck_id}/cards", headers={"Authorization": f"Bearer {token}"})
    assert cards_res.status_code == 200
    cards = cards_res.json()
    assert len(cards) >= 1
    assert cards[0]["topic"] == "Operating Systems"
    assert len(cards[0]["distractors"]) == 3


def test_duplicate_file_upload_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploading the exact same file twice returns 409 DUPLICATE_FILE with the existing deck_id."""
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMSuccess())
    _, token = create_user_and_token(client, "duplicate@example.com")

    content = ("Distributed consensus algorithms such as Paxos and Raft ensure state machine replication.\n\n" * 8).encode("utf-8")

    # First upload
    res1 = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("consensus.txt", content, "text/plain")},
    )
    assert res1.status_code == 200
    deck_id_1 = res1.json()["deck_id"]

    # Second upload of the same content
    res2 = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("consensus.txt", content, "text/plain")},
    )
    assert res2.status_code == 409
    err = res2.json()["error"]
    assert err["code"] == "DUPLICATE_FILE"
    assert err["deck_id"] == deck_id_1


def test_retry_after_failed_job_deletes_empty_deck(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When a job ends in 'failed' with 0 cards, re-uploading the same file deletes the empty deck and retries."""
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMEmpty())
    _, token = create_user_and_token(client, "retryfail@example.com")

    content = ("Compiler construction notes on lexical analysis and context-free grammars.\n\n" * 8).encode("utf-8")

    # First upload produces 0 cards -> job status failed
    res1 = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("compilers.txt", content, "text/plain")},
    )
    assert res1.status_code == 200
    job_id_1 = res1.json()["job_id"]
    deck_id_1 = res1.json()["deck_id"]

    job_res = client.get(f"/api/jobs/{job_id_1}", headers={"Authorization": f"Bearer {token}"})
    assert job_res.json()["status"] == "failed"

    # Now switch to working LLM client and re-upload the same file
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMSuccess())
    res2 = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("compilers.txt", content, "text/plain")},
    )
    # Should NOT be 409 because empty deck was cleaned up
    assert res2.status_code == 200
    deck_id_2 = res2.json()["deck_id"]
    job_id_2 = res2.json()["job_id"]
    assert job_id_2 != job_id_1

    # Verify new job succeeds
    job_res_2 = client.get(f"/api/jobs/{job_id_2}", headers={"Authorization": f"Bearer {token}"})
    assert job_res_2.json()["status"] == "ready"


def test_second_concurrent_upload_returns_job_in_progress(
    client: TestClient, db_session: Session
) -> None:
    """When an active job exists in 'processing' or 'queued', a new upload returns 409 JOB_IN_PROGRESS."""
    user_id, token = create_user_and_token(client, "concurrent@example.com")

    # Manually create a job in 'processing' state
    deck = Deck(user_id=user_id, title="Deck 1", source_filename="deck1.txt", file_hash="hash_concurrent_1")
    db_session.add(deck)
    db_session.flush()

    job = Job(user_id=user_id, deck_id=deck.id, status="processing")
    db_session.add(job)
    db_session.commit()

    content = ("Different text content for another subject.\n\n" * 10).encode("utf-8")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("new_subject.txt", content, "text/plain")},
    )
    assert res.status_code == 409
    err = res.json()["error"]
    assert err["code"] == "JOB_IN_PROGRESS"
    assert err["job_id"] == job.id


def test_job_and_deck_ownership_check(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """User B cannot access or delete User A's jobs, decks, or cards (returns 404)."""
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMSuccess())
    _, token_a = create_user_and_token(client, "usera@example.com")
    _, token_b = create_user_and_token(client, "userb@example.com")

    content = ("Network layers and transport protocols notes.\n\n" * 8).encode("utf-8")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("networks.txt", content, "text/plain")},
    )
    assert res.status_code == 200
    deck_id = res.json()["deck_id"]
    job_id = res.json()["job_id"]

    # User B tries to view User A's job -> 404
    job_res = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert job_res.status_code == 404
    assert job_res.json()["error"]["code"] == "NOT_FOUND"

    # User B tries to view User A's deck cards -> 404
    cards_res = client.get(f"/api/decks/{deck_id}/cards", headers={"Authorization": f"Bearer {token_b}"})
    assert cards_res.status_code == 404
    assert cards_res.json()["error"]["code"] == "NOT_FOUND"

    # User B tries to delete User A's deck -> 404
    del_res = client.delete(f"/api/decks/{deck_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"


def test_decks_listing_and_deletion(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/decks lists own decks with card count, and DELETE /api/decks/{id} deletes the deck."""
    monkeypatch.setattr("app.services.generator.get_llm_client", lambda: MockLLMSuccess())
    _, token = create_user_and_token(client, "deckowner@example.com")

    content = ("Algorithms and data structures lecture notes.\n\n" * 8).encode("utf-8")
    res = client.post(
        "/api/uploads",
        headers={"Authorization": f"Bearer {token}"},
        data={"title": "Data Structures"},
        files={"file": ("dsa.txt", content, "text/plain")},
    )
    assert res.status_code == 200
    deck_id = res.json()["deck_id"]

    # List decks
    decks_res = client.get("/api/decks", headers={"Authorization": f"Bearer {token}"})
    assert decks_res.status_code == 200
    decks = decks_res.json()
    assert len(decks) == 1
    assert decks[0]["id"] == deck_id
    assert decks[0]["title"] == "Data Structures"
    assert decks[0]["card_count"] >= 1

    # Delete deck
    del_res = client.delete(f"/api/decks/{deck_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ok"

    # List decks again -> empty
    decks_after = client.get("/api/decks", headers={"Authorization": f"Bearer {token}"})
    assert decks_after.json() == []


def test_startup_recovery_marks_pending_jobs_failed(db_session: Session) -> None:
    """Stuck jobs in 'queued' or 'processing' are marked failed on lifespan startup."""
    from app.main import lifespan, app
    import asyncio

    # Setup a user and two stuck jobs
    user = User(email="stuck@example.com", password_hash="hash", display_name="Stuck User")
    db_session.add(user)
    db_session.flush()

    job1 = Job(user_id=user.id, status="queued")
    job2 = Job(user_id=user.id, status="processing")
    job3 = Job(user_id=user.id, status="ready", cards_created=5)
    db_session.add_all([job1, job2, job3])
    db_session.commit()

    # Trigger lifespan startup
    async def run_startup():
        async with lifespan(app):
            pass

    asyncio.run(run_startup())

    # Verify statuses
    db_session.refresh(job1)
    db_session.refresh(job2)
    db_session.refresh(job3)

    assert job1.status == "failed"
    assert job1.error_message == "Server restarted during processing"
    assert job2.status == "failed"
    assert job2.error_message == "Server restarted during processing"
    assert job3.status == "ready"
