# RecallOS Phase 3 Design Specification: Upload & Generation Pipeline

## 1. Overview & Scope
Phase 3 builds the core document ingestion and flashcard generation pipeline:
- Server-side file validation for PDF and TXT using magic bytes and size limits (`MAX_UPLOAD_MB`).
- SHA-256 duplicate detection with automatic purge of previously failed empty decks.
- Text extraction with `pypdf` with scanned PDF detection (< 200 characters).
- Chunking on paragraph boundaries (~1500 chars) with small overlap, capped at 40 chunks.
- Pluggable `LLMClient` interface and `GeminiLLMClient` implementation using `GEMINI_MODEL` and direct REST over HTTPX with backoff retry logic.
- Prompt injection defense: treat notes as untrusted user input within delimiters.
- Robust card validation, deduplication, and topic normalization.
- DB-backed background generation job (`FastAPI.BackgroundTasks`) with separate database session and `JobEventPublisher` hook.
- Server restart recovery on app startup.
- REST endpoints: `POST /api/uploads`, `GET /api/jobs/{id}`, `GET /api/decks`, `GET /api/decks/{id}/cards`, `DELETE /api/decks/{id}`.
- Manual test script `scripts/try_upload.py`.
- Automated test suite with mocked LLM and synthetic PDF fixtures.

## 2. File Validation & Extraction (`app/services/extractor.py`)
- **Validation:**
  - File size $\le$ `settings.MAX_UPLOAD_MB * 1024 * 1024`.
  - Empty file check (0 bytes).
  - Magic bytes:
    - PDF: starts with `b"%PDF"`
    - TXT: decodes cleanly via UTF-8
  - Corrupt or password-protected PDF check using `pypdf.PdfReader`:
    - If `reader.is_encrypted`: raise `AppException(400, "PDF_ENCRYPTED", "Password-protected PDFs are not supported")`.
    - If unreadable: raise `AppException(400, "CORRUPT_PDF", "The uploaded PDF file is corrupt or unreadable")`.
- **Extraction:**
  - Extract text across all pages.
  - If `len(extracted_text.strip()) < 200`:
    raise `AppException(400, "SCANNED_PDF", "This looks like a scanned PDF. Please upload a text-based PDF.")`
- **Chunking:**
  - Split text by double newlines (`\n\n`) into paragraphs.
  - Target ~1500 characters per chunk, with ~150 character overlap.
  - Cap at 40 chunks max. If chunks > 40, truncate with warning or raise `PAYLOAD_TOO_LARGE`.

## 3. LLM Client Layer (`app/llm/`)
- `LLMClient` protocol:
  ```python
  class LLMClient(ABC):
      @abstractmethod
      def generate_cards(self, chunk_text: str) -> List[Dict[str, Any]]:
          pass
  ```
- `GeminiLLMClient`:
  - Connects to Google Gemini REST API:
    `POST https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}`
  - Prompt security:
    Wraps text in `<<<UNTRUSTED_STUDY_MATERIAL_START>>> ... <<<UNTRUSTED_STUDY_MATERIAL_END>>>`.
    Instructs model to treat content purely as data to extract flashcards from and ignore any embedded instructions.
  - Response format: JSON array of objects with keys `topic`, `question`, `answer`, `distractors` (array of 3 strings).
  - Retry logic: Max 2 retries (3 attempts total) on 429, 5xx, timeouts, and JSON decode errors with exponential backoff (e.g. 1s, 2s).

## 4. Card Validation & Normalization (`app/services/card_validator.py`)
- Every card must have non-empty `topic`, `question`, `answer`.
- Topic normalized: stripped of whitespace and title-cased.
- Exactly 3 non-empty `distractors`.
- Distractors must all be mutually distinct and case-insensitively distinct from `answer`.
- Case-insensitive deduplication of `question` across the deck.
- Invalid cards are dropped without failing the chunk.

## 5. Background Pipeline & Event Publisher (`app/services/generator.py` & `events.py`)
- `JobEventPublisher` protocol:
  `chunk_done(job_id, chunk_index, total_chunks, new_cards, cards_created)`
  `chunk_failed(job_id, chunk_index, reason)`
  `ready(job_id, deck_id, cards_created)`
  `failed(job_id, error_message)`
- Default: `NullJobEventPublisher`
- Generation loop:
  - Opens dedicated `SessionLocal()`.
  - For each chunk:
    Calls `llm_client.generate_cards()`.
    Validates and persists cards.
    Inserts initial `CardState(user_id=user_id, card_id=card.id, due_date=today_ist(), ease_factor=2.5, interval_days=0, repetitions=0)`.
    Updates `Job.done_chunks` and `Job.cards_created`.
    Emits `chunk_done` or `chunk_failed`.
  - Final status:
    `ready` if `cards_created >= 1`, else `failed`.

## 6. Server Recovery & Concurrency Guard
- Startup event: marks any `jobs` with status in `("queued", "processing")` as `failed` with message `"Server restarted during processing"`.
- Active job limit: only 1 active job per user allowed. Returns 409 `JOB_IN_PROGRESS` if already running.
- Duplicate detection:
  - If existing deck has identical hash:
    - If previous job failed with 0 cards: delete that empty deck and allow re-upload!
    - Otherwise, return 409 `DUPLICATE_DECK` with `existing_deck_id`.
