import io
import pytest
from pypdf import PdfWriter

from app.core.errors import AppException
from app.services.extractor import validate_and_extract_text, chunk_text


def create_blank_pdf_bytes(encrypted: bool = False) -> bytes:
    """Helper creating minimal valid PDF bytes."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if encrypted:
        writer.encrypt("secret123")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_reject_empty_file() -> None:
    """Empty files (0 bytes) are rejected with EMPTY_FILE."""
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(b"", "empty.txt")
    assert exc.value.code == "EMPTY_FILE"
    assert exc.value.status_code == 400


def test_reject_unsupported_file_extension() -> None:
    """Files with non-PDF/TXT extensions are rejected."""
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(b"some content", "file.docx")
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
    assert exc.value.status_code == 400


def test_reject_fake_pdf_extension_without_magic_bytes() -> None:
    """Files named .pdf that don't start with %PDF are rejected."""
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(b"not a real pdf content", "notes.pdf")
    assert exc.value.code == "INVALID_FILE_TYPE"
    assert exc.value.status_code == 400


def test_reject_corrupt_pdf() -> None:
    """Corrupt PDF starting with %PDF but having malformed structure is rejected."""
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(b"%PDF-1.4 corrupt invalid structure", "notes.pdf")
    assert exc.value.code == "CORRUPT_PDF"
    assert exc.value.status_code == 400


def test_reject_encrypted_pdf() -> None:
    """Encrypted/password-protected PDFs are rejected."""
    pdf_bytes = create_blank_pdf_bytes(encrypted=True)
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(pdf_bytes, "protected.pdf")
    assert exc.value.code == "PDF_ENCRYPTED"
    assert exc.value.status_code == 400


def test_reject_scanned_pdf_under_200_chars() -> None:
    """A valid PDF with under 200 characters of extracted text raises SCANNED_PDF."""
    pdf_bytes = create_blank_pdf_bytes(encrypted=False)
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(pdf_bytes, "scanned.pdf")
    assert exc.value.code == "SCANNED_PDF"
    assert "This looks like a scanned PDF. Please upload a text-based PDF." in exc.value.message


def test_reject_scanned_txt_under_200_chars() -> None:
    """Text files under 200 characters are rejected."""
    with pytest.raises(AppException) as exc:
        validate_and_extract_text(b"Short text under 200 chars.", "short.txt")
    assert exc.value.code == "INSUFFICIENT_TEXT"


def test_accept_valid_txt() -> None:
    """Text files with valid UTF-8 and over 200 characters are accepted."""
    long_text = ("This is a comprehensive study guide on distributed systems. " * 10).encode("utf-8")
    assert len(long_text) >= 200
    extracted = validate_and_extract_text(long_text, "notes.txt")
    assert "distributed systems" in extracted


def test_chunking_logic() -> None:
    """Chunking breaks text on paragraph boundaries and caps at 40 chunks."""
    paragraphs = [
        f"Paragraph {i}: " + ("Detailed notes about system architecture. " * 15)
        for i in range(50)
    ]
    full_text = "\n\n".join(paragraphs)

    chunks = chunk_text(full_text, target_size=1500, overlap=100, max_chunks=40)
    assert len(chunks) <= 40
    assert len(chunks) > 1
    # Check that chunks contain text
    assert all(len(c.strip()) > 0 for c in chunks)
