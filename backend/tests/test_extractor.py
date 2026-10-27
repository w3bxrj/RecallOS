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


def create_image_pdf_bytes(num_pages: int = 1) -> bytes:
    """Helper generating an image-only PDF with rendered text on PIL image and no text layer."""
    from PIL import Image, ImageDraw

    images = []
    for i in range(num_pages):
        img = Image.new("RGB", (400, 300), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), f"Handwritten Study Notes Page {i + 1}\nFormula: sqrt(2) and p^2 = 2q^2", fill=(0, 0, 0))
        images.append(img)

    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


def create_text_pdf_bytes(num_pages: int = 1, text_per_page: str = "") -> bytes:
    """Helper creating a PDF with real extractable text using standard Type 1 font."""
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    if not text_per_page:
        text_per_page = "Operating Systems and Distributed Computing Architecture lecture notes. " * 8

    writer = PdfWriter()
    font_dict = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    res_dict = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_dict})
    })

    for _ in range(num_pages):
        page = writer.add_blank_page(width=400, height=400)
        page[NameObject("/Resources")] = res_dict
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text_per_page}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_detection_chooses_vision_for_scanned_and_text_for_normal_pdf() -> None:
    """Detection switches to vision mode for image-only PDF (< 150 chars/page) and text mode for normal PDF."""
    from app.services.extractor import extract_and_detect_mode

    # 1. Image-only PDF
    image_pdf = create_image_pdf_bytes(num_pages=2)
    vision_res = extract_and_detect_mode(image_pdf, "scanned_notes.pdf")
    assert vision_res.mode == "vision"
    assert vision_res.page_count == 2
    assert len(vision_res.text) < 150

    # 2. Normal text-rich PDF
    text_pdf = create_text_pdf_bytes(num_pages=2)
    text_res = extract_and_detect_mode(text_pdf, "textbook.pdf")
    assert text_res.mode == "text"
    assert text_res.page_count == 2
    assert len(text_res.text) >= 150 * 2


def test_split_pdf_into_chunks_10_pages() -> None:
    """A 10-page image PDF is split into 3 chunks of 4, 4, and 2 pages using pypdf."""
    from app.services.extractor import split_pdf_into_chunks
    import pypdf

    ten_page_pdf = create_image_pdf_bytes(num_pages=10)
    chunks, notice = split_pdf_into_chunks(ten_page_pdf, pages_per_chunk=4, max_pages=32)

    assert notice is None
    assert len(chunks) == 3

    # Chunk 1: Pages 1-4
    c0_bytes, c0_label = chunks[0]
    assert c0_label == "Pages 1-4"
    r0 = pypdf.PdfReader(io.BytesIO(c0_bytes))
    assert len(r0.pages) == 4

    # Chunk 2: Pages 5-8
    c1_bytes, c1_label = chunks[1]
    assert c1_label == "Pages 5-8"
    r1 = pypdf.PdfReader(io.BytesIO(c1_bytes))
    assert len(r1.pages) == 4

    # Chunk 3: Pages 9-10
    c2_bytes, c2_label = chunks[2]
    assert c2_label == "Pages 9-10"
    r2 = pypdf.PdfReader(io.BytesIO(c2_bytes))
    assert len(r2.pages) == 2


def test_split_pdf_page_cap_and_notice() -> None:
    """PDF exceeding max_pages is capped and returns the exact notice message."""
    from app.services.extractor import split_pdf_into_chunks
    import pypdf

    # 10 pages capped at 6 pages
    ten_page_pdf = create_image_pdf_bytes(num_pages=10)
    chunks, notice = split_pdf_into_chunks(ten_page_pdf, pages_per_chunk=4, max_pages=6)

    assert notice == "Only the first 6 pages were processed"
    assert len(chunks) == 2

    # Chunk 1: Pages 1-4
    assert chunks[0][1] == "Pages 1-4"
    assert len(pypdf.PdfReader(io.BytesIO(chunks[0][0])).pages) == 4

    # Chunk 2: Pages 5-6 (2 pages remaining up to cap)
    assert chunks[1][1] == "Pages 5-6"
    assert len(pypdf.PdfReader(io.BytesIO(chunks[1][0])).pages) == 2


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
