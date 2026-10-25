# Phase 3 Implementation Plan - Upload & Generation Pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement file validation, pypdf text extraction, chunking, LLMClient interface + Gemini implementation, background generation pipeline with retries, startup recovery, upload/decks REST endpoints, and automated tests.

**Architecture:** Greenfield document processing pipeline with defensive file inspection, modular LLM abstraction using direct REST + exponential backoff, background execution with DB-isolated sessions, and decoupled event hooks preparing for Phase 4 WebSockets.

**Tech Stack:** Python 3.13, FastAPI, pypdf, httpx, SQLAlchemy 2.0, pytest.

**Spec:** docs/superpowers/specs/2026-10-25-phase3-upload-generation-design.md

## Global Constraints
- Allow only PDF (with `%PDF` magic bytes) and TXT (UTF-8 valid).
- Maximum file size `MAX_UPLOAD_MB` (default 10 MB).
- Scanned PDF (< 200 extracted characters) rejected with message `"This looks like a scanned PDF. Please upload a text-based PDF."`.
- Maximum 40 chunks per upload.
- Treat notes text as untrusted: prompt wrapped with delimiters, instructing model to ignore embedded commands.
- Background tasks MUST use their own `SessionLocal()`, never reusing the request session.
- Only one active job per user at a time (`JOB_IN_PROGRESS` on collision).
- Retry after failed empty job purges previous failed deck without triggering 409.
- Mock all LLM calls in automated tests; do not call real external APIs during `pytest`.

## Review Focus
- Scanned PDF with < 200 characters fails with the exact required error message.
- Corrupt and password-protected PDFs are rejected with clear error codes.
- Duplicate upload returns 409 with existing deck ID, but retry after a 0-card failed job succeeds.
- Invalid JSON from LLM retries twice with backoff then skips chunk without failing whole pipeline.
- Cards with invalid distractors or duplicate questions across the deck are dropped.
- Server restart recovery marks orphaned queued/processing jobs as failed.

---

### Task 1: Dependencies, Config & .env.example Update
**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `.env`

- [ ] **Step 1: Add `pypdf==5.1.0` to requirements and install in venv**
- [ ] **Step 2: Add `GEMINI_MODEL: str = "gemini-1.5-flash"` to `Settings`**
- [ ] **Step 3: Update `.env.example` and local `.env` with `GEMINI_MODEL=gemini-1.5-flash`**
- [ ] **Step 4: Commit**
```bash
git add backend/requirements.txt backend/app/core/config.py .env.example
git commit -m "chore(config): add pypdf, GEMINI_MODEL setting, and update env example"
```

---

### Task 2: File Validation, Text Extraction & Chunking
**Files:**
- Create: `backend/app/services/extractor.py`
- Create: `backend/tests/test_extractor.py`

- [ ] **Step 1: Write unit tests in `tests/test_extractor.py`**
Test:
- Valid text extraction from TXT and PDF.
- Magic bytes validation (%PDF, UTF-8).
- Reject empty file.
- Reject corrupt PDF.
- Reject scanned PDF (< 200 chars).
- Paragraph chunking (~1500 chars) with 40-chunk cap.

- [ ] **Step 2: Implement `services/extractor.py`**
Functions: `validate_file_content`, `extract_text_from_file`, `chunk_text`.

- [ ] **Step 3: Run pytest on extractor tests**
Run: `pytest tests/test_extractor.py -v`

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/extractor.py backend/tests/test_extractor.py
git commit -m "feat(extractor): implement file validation, text extraction, and chunking"
```

---

### Task 3: LLM Layer: Interface & Gemini Client
**Files:**
- Create: `backend/app/llm/__init__.py`
- Create: `backend/app/llm/base.py`
- Create: `backend/app/llm/gemini.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Write unit tests with mocked httpx transport in `tests/test_llm.py`**
Test:
- Successful card generation and JSON parsing.
- 429 rate limit retries with exponential backoff.
- 5xx error retries.
- Invalid JSON retries then raises or returns empty.
- Prompt injection isolation delimiters.

- [ ] **Step 2: Implement `llm/base.py` (LLMClient protocol) and `llm/gemini.py`**
Implement `generate_cards(chunk_text: str) -> List[Dict[str, Any]]` with backoff and prompt safety.

- [ ] **Step 3: Run pytest on LLM tests**
Run: `pytest tests/test_llm.py -v`

- [ ] **Step 4: Commit**
```bash
git add backend/app/llm/ backend/tests/test_llm.py
git commit -m "feat(llm): implement LLMClient interface and Gemini client with backoff"
```

---

### Task 4: Card Validation, Deduplication & Topic Normalization
**Files:**
- Create: `backend/app/services/card_validator.py`
- Create: `backend/tests/test_card_validator.py`

- [ ] **Step 1: Write unit tests in `tests/test_card_validator.py`**
Test:
- Topic normalization (trim, title-case).
- Valid card passes.
- Missing fields rejected.
- Distractors count != 3 rejected.
- Distractor identical to answer rejected.
- Duplicate distractors rejected.
- Duplicate question across deck dropped.

- [ ] **Step 2: Implement `services/card_validator.py`**
Implement `validate_and_normalize_card(raw_card, seen_questions)`.

- [ ] **Step 3: Run pytest on card validator tests**
Run: `pytest tests/test_card_validator.py -v`

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/card_validator.py backend/tests/test_card_validator.py
git commit -m "feat(validation): add card validation, deduplication, and topic normalization"
```

---

### Task 5: Event Publisher & Background Generation Pipeline
**Files:**
- Create: `backend/app/services/events.py`
- Create: `backend/app/services/generator.py`

- [ ] **Step 1: Implement `services/events.py`**
`JobEventPublisher` protocol and `NullJobEventPublisher`.

- [ ] **Step 2: Implement `services/generator.py`**
`run_card_generation(job_id, user_id, deck_id, chunks, llm_client, publisher)`:
- Opens dedicated session `SessionLocal()`.
- Updates `Job.status = "processing"`.
- Loops through chunks, validates cards, inserts `Card` and `CardState`.
- Updates `Job.done_chunks` and `Job.cards_created`.
- Sets `Job.status = "ready"` or `"failed"`.
- Calls event publisher hooks.

- [ ] **Step 3: Commit**
```bash
git add backend/app/services/events.py backend/app/services/generator.py
git commit -m "feat(generator): implement background card generation pipeline and event publisher"
```

---

### Task 6: Server Startup Recovery Lifecycle & Concurrency Guard
**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement lifespan context manager in `main.py`**
On startup, marks stuck jobs ("queued", "processing") as failed with `"Server restarted during processing"`.

- [ ] **Step 2: Commit**
```bash
git add backend/app/main.py
git commit -m "feat(core): add server restart recovery for jobs and concurrent upload guard"
```

---

### Task 7: Endpoints: Uploads, Jobs & Decks Management
**Files:**
- Create: `backend/app/schemas/upload.py`
- Create: `backend/app/schemas/deck.py`
- Create: `backend/app/routers/uploads.py`
- Create: `backend/app/routers/decks.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement `POST /api/uploads` and `GET /api/jobs/{id}` in `routers/uploads.py`**
Include SHA-256 duplicate check (and retry after failed empty job purge) and active job limit check.

- [ ] **Step 2: Implement `GET /api/decks`, `GET /api/decks/{id}/cards`, `DELETE /api/decks/{id}` in `routers/decks.py`**
Include ownership check (404 for other users' decks).

- [ ] **Step 3: Register routers in `main.py`**

- [ ] **Step 4: Commit**
```bash
git add backend/app/schemas/upload.py backend/app/schemas/deck.py backend/app/routers/uploads.py backend/app/routers/decks.py backend/app/main.py
git commit -m "feat(api): implement upload, job status, and decks management endpoints"
```

---

### Task 8: Manual E2E Upload Script
**Files:**
- Create: `backend/scripts/try_upload.py`

- [ ] **Step 1: Implement `scripts/try_upload.py`**
CLI script accepting a file path, logging in, uploading to `/api/uploads`, and polling `/api/jobs/{id}` with live progress.

- [ ] **Step 2: Commit**
```bash
git add backend/scripts/try_upload.py
git commit -m "chore(scripts): add manual upload testing script"
```

---

### Task 9: Comprehensive Integration Tests & Verification
**Files:**
- Create: `backend/tests/test_upload.py`

- [ ] **Step 1: Implement integration tests in `tests/test_upload.py`**
Test:
- Duplicate upload returns 409 with deck id.
- Retry after failed empty job succeeds.
- Scanned PDF rejected with expected message.
- Corrupt PDF rejected.
- Invalid file type rejected.
- Second concurrent upload returns 409 `JOB_IN_PROGRESS`.
- Partial chunk failure skips chunk and finishes remaining.
- Decks list, deck cards, and delete deck with cascade.
- Ownership checks on decks and jobs.

- [ ] **Step 2: Run all tests in the test suite and confirm 100% pass rate**
Run: `pytest tests -v`

- [ ] **Step 3: Commit**
```bash
git add backend/tests/test_upload.py
git commit -m "test(upload): add integration tests for upload pipeline, duplicate check, and error recovery"
```
