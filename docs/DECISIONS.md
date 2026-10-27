# Architecture Decision Records (ADRs)

## ADR 001: Native Gemini Vision PDF Fallback for Scanned Documents

### Status
Accepted (Phase 7 - Scanned PDF Vision Fallback)

### Context & Problem Statement
A significant proportion of student study materials consist of scanned textbook pages, handwritten lecture notes, or camera captures exported as PDF documents. In these files, there is little to no extractable digital text (frequently fewer than 150 characters per page). Previously, the generation pipeline aborted such uploads with `SCANNED_PDF: "This looks like a scanned PDF"`.

We needed a robust, production-ready solution to ingest and generate high-yield flashcards from scanned and image-only PDFs while deploying reliably on Render's slim Linux runtime.

---

### Options Considered

1. **System-level OCR Library (Tesseract OCR + Poppler / pdf2image)**
   - *Pros:* Local processing, no additional external API cost.
   - *Cons:* Requires installing system packages (`apt-get install tesseract-ocr poppler-utils`) and heavy image processing libraries. Render's free/starter Linux runtime is a slim container without root apt access during standard Python builds. Furthermore, Tesseract struggles significantly with student handwriting, mathematical notation, and complex multi-column slide layouts.

2. **Two-Stage Cloud OCR + Text LLM (e.g. Google Cloud Vision API followed by Gemini text)**
   - *Pros:* High quality character extraction.
   - *Cons:* Adds secondary cloud credentials, separate billing, network roundtrips, and still produces unstructured intermediate text that loses visual spatial relationships (e.g., diagrams, equation formatting).

3. **Direct Native Gemini 1.5 Multimodal PDF Vision Processing**
   - *Pros:*
     - **Zero system packages:** Sub-PDFs are sliced purely in Python memory using `pypdf` (`PdfWriter`). Works out-of-the-box on Render's slim Linux container without external binaries.
     - **Handwriting & Math Notation:** Gemini 1.5 multimodal vision excels at reading messy handwriting, mathematical formulae, and diagrams directly in visual context.
     - **Direct-to-Card Generation:** Eliminates intermediate OCR transcription errors; the model directly applies pedagogical flashcard extraction to the scanned pages.
   - *Cons:* Increased inference latency and tighter Gemini API rate limits.

---

### Decision
We chose **Option 3: Direct Native Gemini 1.5 Multimodal PDF Vision Processing**.

When a PDF has an average of fewer than 150 extracted characters per page, RecallOS automatically switches the job to **Vision Mode**:
1. Slices the document into 4-page sub-PDFs using `pypdf.PdfWriter` (zero external dependencies).
2. Caps processing at `MAX_VISION_PAGES` (default 32 pages, max 8 chunks) and attaches a transparent user notice (`"Only the first 32 pages were processed"`).
3. Transmits sub-PDFs as base64-encoded `inline_data` (`application/pdf`) to Gemini 1.5 Flash with a 90-second timeout.
4. Enforces a 6-second cooldown between consecutive vision chunks to strictly respect Gemini free-tier rate limits.
5. Emits real-time live events (`"Pages 1-4"`, `"Reading scanned pages..."`) over WebSockets.

---

### Trade-offs & Mitigations

| Trade-off | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Latency** | Vision chunks take ~10–20s per 4 pages (vs ~1–3s for text). | Chunks are streamed in real-time over WebSockets with live progress bars and `"Reading scanned pages..."` status badges. |
| **Quota & Rate Limits** | Multimodal calls have tighter RPM and TPM limits on Gemini free tier. | Capped at `MAX_VISION_PAGES` (default 32 pages), with an enforced 6.0-second delay between vision chunks. |
| **Privacy & Data Governance** | Document page images are sent to Google's Gemini API endpoints. | PDF bytes are sent encrypted over TLS to Gemini's generative language API endpoints. No user documents are persisted on external third-party disk storage. Mentioned in documentation and privacy policies. |

---

## ADR 002: Dynamic Gemini Model Configuration, Header Authentication & Secret Redaction

### Status
Accepted (Security and Robustness Fix)

### Context & Problem Statement
1. **Model Retirement Lifecycle:** Google AI Studio periodically retires and replaces model checkpoints (e.g. older 1.5 variants or preview releases). If model names are hardcoded, a retired model returns HTTP 404 and breaks generation until code is changed and redeployed.
2. **Credential Leakage via URL Query Parameters:** Passing Gemini API keys as URL query parameters (`?key=...`) causes HTTP clients (like `httpx`) to include the full query string in standard exception strings upon network, timeout, or HTTP status errors. If unhandled or logged directly, this leaks the secret into `jobs.error_message`, WebSocket events, and client API responses.
3. **Information Disclosure in Database Records:** Raw exception strings in database records expose internal API endpoints, stack details, or credentials.

### Decision
1. **Dynamic Model Configuration via Environment Variable:**
   `GEMINI_MODEL` is kept strictly as an environment variable (default: `gemini-2.5-flash`). It is never hardcoded in request URLs or business logic. At server startup in production, a non-blocking HEAD/GET check pings Google's `/models/{GEMINI_MODEL}` endpoint with a 5s timeout; if HTTP 404 is returned, a warning is logged immediately alerting operators to update the model environment variable.
2. **Header-Based Authentication:**
   All calls to Google's Gemini API authenticate exclusively via the `x-goog-api-key` request header. Keys are never appended as URL query strings.
3. **Centralized Secret Redaction:**
   A central `redact()` helper removes Google API keys (`AIza...`, `AQ....`), URL `key=` values, Authorization/Bearer headers, and configured environment secrets (`GEMINI_API_KEY`, `JWT_SECRET`) from any string before logging, storing, or transmitting over APIs.
4. **Clean Human-Readable Error Messages & Fail-Fast:**
   `jobs.error_message` never stores raw exception text. Specific Gemini error statuses are mapped directly to human-friendly messages:
   - `404` (model unavailable): `"The AI service is temporarily unavailable. Please try again later."` (Fail-fast, server logs error with model name and job context).
   - `401 / 403` (credential issue): `"AI service configuration problem"` (Fail-fast).
   - `429 / 5xx` (exhausted retries): `"The AI service is busy. Please try again in a minute."`

