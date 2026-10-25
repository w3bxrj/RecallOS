import io
import logging
from typing import List
import pypdf

from app.core.config import settings
from app.core.errors import AppException

logger = logging.getLogger(__name__)


def validate_and_extract_text(file_bytes: bytes, filename: str) -> str:
    """Validates uploaded file size and content magic bytes, and extracts text.

    Supports text-based PDF and UTF-8 TXT files.
    """
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise AppException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_MB} MB",
        )

    if len(file_bytes) == 0:
        raise AppException(
            status_code=400,
            code="EMPTY_FILE",
            message="The uploaded file is empty",
        )

    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        # Check PDF magic bytes (%PDF)
        if not file_bytes.startswith(b"%PDF"):
            raise AppException(
                status_code=400,
                code="INVALID_FILE_TYPE",
                message="File extension is .pdf but file content does not have a valid %PDF header",
            )

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                raise AppException(
                    status_code=400,
                    code="PDF_ENCRYPTED",
                    message="Password-protected PDFs are not supported. Please upload an unencrypted file.",
                )

            extracted_pages: List[str] = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text.strip())

            full_text = "\n\n".join(extracted_pages).strip()
        except AppException:
            raise
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            raise AppException(
                status_code=400,
                code="CORRUPT_PDF",
                message="The uploaded PDF file is corrupt or unreadable.",
            )

        # Scanned PDF check (< 200 characters)
        if len(full_text) < 200:
            raise AppException(
                status_code=400,
                code="SCANNED_PDF",
                message="This looks like a scanned PDF. Please upload a text-based PDF.",
            )

        return full_text

    elif lower_name.endswith(".txt"):
        try:
            full_text = file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise AppException(
                status_code=400,
                code="INVALID_ENCODING",
                message="Text file must be encoded in UTF-8 format.",
            )

        if len(full_text) < 200:
            raise AppException(
                status_code=400,
                code="INSUFFICIENT_TEXT",
                message="The uploaded text is under 200 characters, which is insufficient to generate flashcards.",
            )

        return full_text

    else:
        raise AppException(
            status_code=400,
            code="UNSUPPORTED_FILE_TYPE",
            message="Only PDF (.pdf) and Text (.txt) files are supported.",
        )


def chunk_text(
    text: str,
    target_size: int = 1500,
    overlap: int = 150,
    max_chunks: int = 40,
) -> List[str]:
    """Splits extracted text into coherent chunks of roughly target_size characters

    on paragraph boundaries, with a small overlap between chunks.
    Caps at max_chunks to protect LLM quota.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for p in paragraphs:
        p_len = len(p)
        if current_len + p_len > target_size and current_chunk:
            chunk_str = "\n\n".join(current_chunk)
            chunks.append(chunk_str)

            # Build overlap from the tail of the current chunk
            overlap_prefix = chunk_str[-overlap:] if len(chunk_str) > overlap else ""
            current_chunk = [overlap_prefix, p] if overlap_prefix else [p]
            current_len = len(overlap_prefix) + p_len
        else:
            current_chunk.append(p)
            current_len += p_len + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    # Enforce maximum chunk limit
    if len(chunks) > max_chunks:
        logger.warning(
            "Document produced %d chunks, truncating to maximum allowed of %d chunks.",
            len(chunks),
            max_chunks,
        )
        chunks = chunks[:max_chunks]

    return [c.strip() for c in chunks if c.strip()]
