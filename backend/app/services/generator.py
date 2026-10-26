import io
import logging
import time
from typing import List, Optional, Set
import pypdf
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.time import today_ist, now_ist
from app.llm.base import LLMClient
from app.llm.gemini import GeminiLLMClient
from app.models.job import Job
from app.models.card import Card
from app.models.card_state import CardState
from app.services.card_validator import validate_card
from app.services.events import JobEventPublisher, default_event_publisher
from app.services.extractor import chunk_text
from app.ws.publisher import ws_publisher

logger = logging.getLogger(__name__)


def get_llm_client() -> LLMClient:
    """Factory function for LLM client (can be overridden in tests)."""
    return GeminiLLMClient()


def get_event_publisher() -> JobEventPublisher:
    """Factory function for event publisher (defaults to WebSocket publisher in production)."""
    return ws_publisher


def run_card_generation(
    job_id: int,
    user_id: int,
    deck_id: int,
    chunks: List[str],
    llm_client: Optional[LLMClient] = None,
    publisher: Optional[JobEventPublisher] = None,
    delay_between_chunks: float = 0.5,
) -> None:
    """Background task function processing text chunks into flashcards.

    MUST open its own database session and manage its own transaction lifecycle.
    """
    if llm_client is None:
        llm_client = get_llm_client()
    if publisher is None:
        publisher = get_event_publisher()

    db = SessionLocal()
    today = today_ist()

    try:
        job = db.get(Job, job_id)
        if not job:
            logger.error("Job %d not found in database.", job_id)
            return

        job.status = "processing"
        job.total_chunks = len(chunks)
        db.commit()

        # Track questions already present in this deck to avoid duplicates
        existing_questions = db.scalars(
            select(Card.question).where(Card.deck_id == deck_id)
        ).all()
        seen_questions: Set[str] = {q.strip().lower() for q in existing_questions}

        for idx, chunk in enumerate(chunks):
            if idx > 0 and delay_between_chunks > 0:
                time.sleep(delay_between_chunks)

            try:
                raw_cards = llm_client.generate_cards(chunk)
                valid_cards = []
                for raw_c in raw_cards:
                    validated = validate_card(raw_c, seen_questions)
                    if validated:
                        valid_cards.append(validated)

                if valid_cards:
                    for v in valid_cards:
                        card_obj = Card(
                            deck_id=deck_id,
                            topic=v["topic"],
                            question=v["question"],
                            answer=v["answer"],
                            distractors=v["distractors"],
                        )
                        db.add(card_obj)
                        db.flush()

                        state_obj = CardState(
                            card_id=card_obj.id,
                            user_id=user_id,
                            ease_factor=2.5,
                            interval_days=0,
                            repetitions=0,
                            due_date=today,
                            lapses=0,
                        )
                        db.add(state_obj)

                    job.cards_created += len(valid_cards)
                    job.done_chunks = idx + 1
                    db.commit()

                    publisher.chunk_done(
                        job_id=job_id,
                        chunk_index=idx,
                        total_chunks=len(chunks),
                        new_cards=valid_cards,
                        cards_created=job.cards_created,
                    )
                else:
                    job.done_chunks = idx + 1
                    db.commit()
                    publisher.chunk_failed(
                        job_id=job_id,
                        chunk_index=idx,
                        reason="No valid cards extracted from chunk",
                    )

            except Exception as chunk_exc:
                logger.warning("Chunk %d failed in job %d: %s", idx, job_id, chunk_exc)
                job.done_chunks = idx + 1
                db.commit()
                publisher.chunk_failed(
                    job_id=job_id,
                    chunk_index=idx,
                    reason=str(chunk_exc),
                )

        # Complete job
        job.finished_at = now_ist()
        if job.cards_created >= 1:
            job.status = "ready"
            db.commit()
            publisher.ready(
                job_id=job_id,
                deck_id=deck_id,
                cards_created=job.cards_created,
            )
            logger.info("Job %d completed successfully with %d cards.", job_id, job.cards_created)
        else:
            job.status = "failed"
            job.error_message = "No valid flashcards could be generated from the document."
            db.commit()
            publisher.failed(job_id=job_id, message=job.error_message)
            logger.warning("Job %d marked failed (0 cards created).", job_id)

    except Exception as exc:
        logger.exception("Unexpected exception in background generation job %d: %s", job_id, exc)
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error_message = f"Generation failed unexpectedly: {str(exc)}"
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job_id, message=job.error_message)
        except Exception:
            pass
    finally:
        db.close()


def process_upload_pipeline(
    job_id: int,
    user_id: int,
    deck_id: int,
    file_bytes: bytes,
    filename: str,
    llm_client: Optional[LLMClient] = None,
    publisher: Optional[JobEventPublisher] = None,
    delay_between_chunks: float = 0.5,
) -> None:
    """Full background pipeline from raw file bytes to generated flashcards."""
    if llm_client is None:
        llm_client = get_llm_client()
    if publisher is None:
        publisher = get_event_publisher()

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return

        job.status = "processing"
        db.commit()

        lower_name = filename.lower()
        full_text = ""
        if lower_name.endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_text = []
                for p in reader.pages:
                    text = p.extract_text()
                    if text:
                        pages_text.append(text.strip())
                full_text = "\n\n".join(pages_text).strip()
            except Exception as exc:
                job.status = "failed"
                job.error_message = f"Failed to extract text from PDF: {str(exc)}"
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job.id, message=job.error_message)
                return
        elif lower_name.endswith(".txt"):
            try:
                full_text = file_bytes.decode("utf-8").strip()
            except Exception as exc:
                job.status = "failed"
                job.error_message = f"Failed to decode text file: {str(exc)}"
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job.id, message=job.error_message)
                return

        if len(full_text) < 200:
            job.status = "failed"
            job.error_message = "This looks like a scanned PDF. Please upload a text-based PDF."
            job.finished_at = now_ist()
            db.commit()
            publisher.failed(job_id=job.id, message=job.error_message)
            return

        chunks = chunk_text(full_text, target_size=1500, overlap=150, max_chunks=40)
        job.total_chunks = len(chunks)
        db.commit()

    finally:
        db.close()

    run_card_generation(
        job_id=job_id,
        user_id=user_id,
        deck_id=deck_id,
        chunks=chunks,
        llm_client=llm_client,
        publisher=publisher,
        delay_between_chunks=delay_between_chunks,
    )
