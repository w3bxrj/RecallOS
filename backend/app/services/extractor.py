from dataclasses import dataclass
import io
import logging
from typing import List, Optional, Tuple
import pypdf

from app.core.config import settings
from app.core.errors import AppException

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of document validation and text/vision mode extraction."""
    mode: str  # "text" or "vision"
    text: str = ""
    page_count: int = 0


def extract_and_detect_mode(file_bytes: bytes, filename: str) -> ExtractionResult:
    """Validates uploaded file and detects whether to process via text or vision mode.

    Detection rule:
    - Text files (.txt) are processed in text mode (min 200 chars).
    - PDFs are inspected: average extracted characters per page is computed.
      If avg_chars_per_page >= 150, text mode is chosen.
      If avg_chars_per_page < 150, vision mode is chosen.
    - Preserves errors for corrupt, encrypted, empty, or unsupported files.
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

            page_count = len(reader.pages)
            if page_count == 0:
                raise AppException(
                    status_code=400,
                    code="CORRUPT_PDF",
                    message="The uploaded PDF file is corrupt or unreadable.",
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

        # Compute average extracted characters per page
        avg_chars_per_page = len(full_text) / page_count

        if avg_chars_per_page >= 150:
            return ExtractionResult(mode="text", text=full_text, page_count=page_count)
        else:
            logger.info(
                "PDF '%s' has avg %.1f chars/page (< 150). Switching to VISION MODE.",
                filename,
                avg_chars_per_page,
            )
            return ExtractionResult(mode="vision", text=full_text, page_count=page_count)

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

        return ExtractionResult(mode="text", text=full_text, page_count=1)

    else:
        raise AppException(
            status_code=400,
            code="UNSUPPORTED_FILE_TYPE",
            message="Only PDF (.pdf) and Text (.txt) files are supported.",
        )


def validate_and_extract_text(file_bytes: bytes, filename: str) -> str:
    """Backward-compatible helper that validates file and extracts text.

    For text mode, returns the extracted text string.
    For vision mode, returns the partial text or empty string.
    """
    result = extract_and_detect_mode(file_bytes, filename)
    return result.text


def split_pdf_into_chunks(
    file_bytes: bytes,
    pages_per_chunk: int = 4,
    max_pages: Optional[int] = None,
) -> Tuple[List[Tuple[bytes, str]], Optional[str]]:
    """Splits a PDF into sub-PDFs of up to pages_per_chunk using pypdf only.

    Caps at max_pages (default settings.MAX_VISION_PAGES).
    If the PDF has more pages, processes only the first max_pages and generates a notice.
    Returns:
        (chunks, notice)
        where chunks is a list of (sub_pdf_bytes, page_range_label)
        and notice is "Only the first N pages were processed" or None.
    """
    if max_pages is None:
        max_pages = settings.MAX_VISION_PAGES

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return [], None

    notice: Optional[str] = None
    pages_to_process = total_pages
    if total_pages > max_pages:
        pages_to_process = max_pages
        notice = f"Only the first {max_pages} pages were processed"

    chunks: List[Tuple[bytes, str]] = []
    for start_idx in range(0, pages_to_process, pages_per_chunk):
        end_idx = min(start_idx + pages_per_chunk, pages_to_process)
        writer = pypdf.PdfWriter()
        for page_idx in range(start_idx, end_idx):
            writer.add_page(reader.pages[page_idx])

        buf = io.BytesIO()
        writer.write(buf)
        sub_pdf_bytes = buf.getvalue()

        start_page = start_idx + 1
        end_page = end_idx
        if start_page == end_page:
            label = f"Pages {start_page}"
        else:
            label = f"Pages {start_page}-{end_page}"

        chunks.append((sub_pdf_bytes, label))

    return chunks, notice


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
