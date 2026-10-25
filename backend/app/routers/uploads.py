import io
import hashlib
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, func
import pypdf

from app.core.config import settings
from app.core.db import get_db
from app.core.errors import AppException
from app.routers.deps import get_current_user
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.job import Job
from app.schemas.upload import UploadResponse, JobResponse
from app.services.generator import process_upload_pipeline

router = APIRouter(tags=["Uploads & Jobs"])


@router.post("/uploads", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Uploads a document (PDF or TXT) and enqueues card generation."""
    filename = file.filename or "upload.pdf"
    lower_name = filename.lower()

    if not (lower_name.endswith(".pdf") or lower_name.endswith(".txt")):
        raise AppException(
            status_code=400,
            code="UNSUPPORTED_FILE_TYPE",
            message="Only PDF (.pdf) and Text (.txt) files are supported.",
        )

    content = await file.read()

    if len(content) == 0:
        raise AppException(
            status_code=400,
            code="EMPTY_FILE",
            message="The uploaded file is empty",
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise AppException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_MB} MB",
        )

    if lower_name.endswith(".pdf"):
        if not content.startswith(b"%PDF"):
            raise AppException(
                status_code=400,
                code="CORRUPT_PDF",
                message="File does not start with valid %PDF header.",
            )
        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise AppException(
                    status_code=400,
                    code="PDF_ENCRYPTED",
                    message="Password-protected PDFs are not supported. Please upload an unencrypted file.",
                )
        except AppException:
            raise
        except Exception:
            raise AppException(
                status_code=400,
                code="CORRUPT_PDF",
                message="The uploaded PDF file is corrupt or unreadable.",
            )

    elif lower_name.endswith(".txt"):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise AppException(
                status_code=400,
                code="INVALID_ENCODING",
                message="Text file must be encoded in UTF-8 format.",
            )

    # SHA-256 duplicate detection
    file_hash = hashlib.sha256(content).hexdigest()
    existing_deck = db.scalar(
        select(Deck).where(Deck.user_id == current_user.id, Deck.file_hash == file_hash)
    )
    if existing_deck:
        card_count = db.scalar(
            select(func.count(Card.id)).where(Card.deck_id == existing_deck.id)
        ) or 0
        if card_count == 0:
            # Delete empty deck so the user can retry without duplicate error
            db.delete(existing_deck)
            db.commit()
        else:
            raise AppException(
                status_code=409,
                code="DUPLICATE_FILE",
                message="You have already uploaded this document.",
                details={"deck_id": existing_deck.id},
            )

    # Check for active job for this user
    active_job = db.scalar(
        select(Job).where(
            Job.user_id == current_user.id,
            Job.status.in_(["queued", "processing"]),
        )
    )
    if active_job:
        raise AppException(
            status_code=409,
            code="JOB_IN_PROGRESS",
            message="You already have a document generation job in progress.",
        )

    # Create Deck and Job
    deck_title = title.strip() if title and title.strip() else filename
    new_deck = Deck(
        user_id=current_user.id,
        title=deck_title,
        source_filename=filename,
        file_hash=file_hash,
    )
    db.add(new_deck)
    db.flush()

    new_job = Job(
        user_id=current_user.id,
        deck_id=new_deck.id,
        status="queued",
        total_chunks=0,
        done_chunks=0,
        cards_created=0,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_deck)
    db.refresh(new_job)

    # Launch background task
    background_tasks.add_task(
        process_upload_pipeline,
        job_id=new_job.id,
        user_id=current_user.id,
        deck_id=new_deck.id,
        file_bytes=content,
        filename=filename,
    )

    return UploadResponse(deck_id=new_deck.id, job_id=new_job.id)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Returns the current status of a generation job (ownership checked)."""
    job = db.scalar(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    if not job:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message="Job not found",
        )
    return job
