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
