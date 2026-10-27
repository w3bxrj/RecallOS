import io
import logging
import time
from typing import List, Optional, Set, Tuple
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import AppException
from app.core.redact import redact
from app.core.time import today_ist, now_ist
from app.llm.base import LLMClient
from app.llm.gemini import GeminiLLMClient, GeminiServiceError
from app.models.job import Job
from app.models.card import Card
from app.models.card_state import CardState
from app.services.card_validator import validate_card
from app.services.events import JobEventPublisher, default_event_publisher
from app.services.extractor import chunk_text, extract_and_detect_mode, split_pdf_into_chunks
from app.ws.publisher import ws_publisher

logger = logging.getLogger(__name__)

DEFAULT_VISION_DELAY = 6.0
DEFAULT_TEXT_DELAY = 0.5


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

            except GeminiServiceError as gse:
                if gse.status_code == 404:
                    logger.error(
                        "GEMINI_MODEL is unavailable, update the env var (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                elif gse.status_code in (401, 403):
                    logger.error(
                        "GEMINI_MODEL configuration problem (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                else:
                    logger.error(
                        "Gemini service error: %s (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        gse.user_message,
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                # Fail fast on 404/401/403 or exhausted retry: do not continue chunk loop
                job.status = "failed"
                job.error_message = gse.user_message
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job_id, message=job.error_message)
                return

            except Exception as chunk_exc:
                logger.warning("Chunk %d failed in job %d: %s", idx, job_id, redact(str(chunk_exc)))
                job.done_chunks = idx + 1
                db.commit()
                publisher.chunk_failed(
                    job_id=job_id,
                    chunk_index=idx,
                    reason="Card extraction failed for this chunk",
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
        logger.exception("Unexpected exception in background generation job %d: %s", job_id, redact(str(exc)))
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error_message = "An unexpected error occurred during flashcard generation. Please try again."
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job_id, message=job.error_message)
        except Exception:
            pass
    finally:
        db.close()


def run_vision_card_generation(
    job_id: int,
    user_id: int,
    deck_id: int,
    chunks: List[Tuple[bytes, str]],
    llm_client: Optional[LLMClient] = None,
    publisher: Optional[JobEventPublisher] = None,
    delay_between_chunks: float = 6.0,
) -> None:
    """Processes sub-PDF chunks into flashcards via LLM vision model.

    Enforces at least 6s delay between chunks in production to respect free-tier rate limits.
    Reuses card validation, distractor checks, deduplication across deck, topic normalization,
    card_states creation, and JobEventPublisher events.
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
        job.is_vision = True
        job.total_chunks = len(chunks)
        db.commit()

        # Track questions already present in this deck to avoid duplicates
        existing_questions = db.scalars(
            select(Card.question).where(Card.deck_id == deck_id)
        ).all()
        seen_questions: Set[str] = {q.strip().lower() for q in existing_questions}

        for idx, (sub_pdf_bytes, page_range_label) in enumerate(chunks):
            if idx > 0 and delay_between_chunks > 0:
                time.sleep(delay_between_chunks)

            try:
                raw_cards = llm_client.generate_cards_from_pdf(sub_pdf_bytes, page_range_label)
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
                        page_range=page_range_label,
                    )
                else:
                    # Empty list or no study content in this chunk is NOT an error
                    job.done_chunks = idx + 1
                    db.commit()
                    publisher.chunk_done(
                        job_id=job_id,
                        chunk_index=idx,
                        total_chunks=len(chunks),
                        new_cards=[],
                        cards_created=job.cards_created,
                        page_range=page_range_label,
                    )

            except GeminiServiceError as gse:
                if gse.status_code == 404:
                    logger.error(
                        "GEMINI_MODEL is unavailable, update the env var (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                elif gse.status_code in (401, 403):
                    logger.error(
                        "GEMINI_MODEL configuration problem (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                else:
                    logger.error(
                        "Gemini service error: %s (job_id=%s, chunk_index=%s, status=%s, model=%s)",
                        gse.user_message,
                        job_id,
                        idx,
                        gse.status_code,
                        gse.model_name,
                    )
                # Fail fast on 404/401/403 or exhausted retry: do not continue chunk loop
                job.status = "failed"
                job.error_message = gse.user_message
                job.finished_at = now_ist()
                db.commit()
                publisher.failed(job_id=job_id, message=job.error_message)
                return

            except Exception as chunk_exc:
                logger.warning(
                    "Vision chunk %d (%s) failed in job %d: %s",
                    idx,
                    page_range_label,
                    job_id,
                    redact(str(chunk_exc)),
                )
                job.done_chunks = idx + 1
                db.commit()
                publisher.chunk_failed(
                    job_id=job_id,
                    chunk_index=idx,
                    reason="Card extraction failed for this chunk",
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
            logger.info("Job %d completed successfully with %d cards in vision mode.", job_id, job.cards_created)
        else:
            job.status = "failed"
            job.error_message = "We could not find readable study content in this PDF. Try a clearer scan or a text-based PDF."
            db.commit()
            publisher.failed(job_id=job_id, message=job.error_message)
            logger.warning("Job %d marked failed (0 cards created in vision mode).", job_id)

    except Exception as exc:
        logger.exception("Unexpected exception in background vision generation job %d: %s", job_id, redact(str(exc)))
        try:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error_message = "An unexpected error occurred during flashcard generation. Please try again."
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
    delay_between_chunks: Optional[float] = None,
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

        try:
            doc = extract_and_detect_mode(file_bytes, filename)
        except AppException as app_exc:
            job.status = "failed"
            job.error_message = app_exc.message
            job.finished_at = now_ist()
            db.commit()
            publisher.failed(job_id=job.id, message=job.error_message)
            return
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Failed to extract text from document: {str(exc)}"
            job.finished_at = now_ist()
            db.commit()
            publisher.failed(job_id=job.id, message=job.error_message)
            return

        if doc.mode == "vision":
            vision_chunks, notice = split_pdf_into_chunks(
                file_bytes,
                pages_per_chunk=4,
                max_pages=settings.MAX_VISION_PAGES,
            )
            job.is_vision = True
            job.total_chunks = len(vision_chunks)
            job.notice = notice
            db.commit()

            vision_delay = delay_between_chunks if delay_between_chunks is not None else DEFAULT_VISION_DELAY
            run_vision_card_generation(
                job_id=job_id,
                user_id=user_id,
                deck_id=deck_id,
                chunks=vision_chunks,
                llm_client=llm_client,
                publisher=publisher,
                delay_between_chunks=vision_delay,
            )
            return

        # Text mode
        text_chunks = chunk_text(doc.text, target_size=1500, overlap=150, max_chunks=40)
        job.is_vision = False
        job.total_chunks = len(text_chunks)
        db.commit()

        text_delay = delay_between_chunks if delay_between_chunks is not None else DEFAULT_TEXT_DELAY
        run_card_generation(
            job_id=job_id,
            user_id=user_id,
            deck_id=deck_id,
            chunks=text_chunks,
            llm_client=llm_client,
            publisher=publisher,
            delay_between_chunks=text_delay,
        )

    finally:
        db.close()
