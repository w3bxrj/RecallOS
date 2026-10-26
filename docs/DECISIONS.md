# Architecture & Design Decisions (docs/DECISIONS.md)

This log records architectural decisions, trade-offs, and rationale for RecallOS.

## ADR-001: Python Runtime & Deployment Target
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** System has Python 3.13 installed. Render backend deployment runs Python (specified in runtime/config).
- **Decision:** Target Python 3.13 runtime compatibility with pinned dependencies in `backend/requirements.txt`. Specify `PYTHON_VERSION=3.13.0` in deployment configuration so Render and local environments match.

## ADR-002: Dual Database Strategy for Dev/Prod vs Pytest
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Production and Dev use PostgreSQL (Neon free tier). Requiring network access to Neon during every unit test execution slows tests down and introduces offline fragility.
- **Decision:** Use generic portable SQLAlchemy types (`JSON` instead of PG-specific `JSONB`, portable timestamps and autoincrements). Unit tests run against an in-memory SQLite database (`sqlite:///:memory:`). Alembic migrations and production run against PostgreSQL. Before marking phases complete, Alembic migrations are validated against PostgreSQL.

## ADR-003: Auth Stack: Native bcrypt + PyJWT
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** `passlib` is unmaintained and throws warnings/errors on modern Python (3.12+ and 3.13), and `python-jose` has unmaintained dependencies.
- **Decision:** Use native `bcrypt` library directly for password hashing. Explicitly validate that passwords do not exceed bcrypt's 72-byte limit (rejecting inputs longer than 72 bytes with code `PASSWORD_TOO_LONG`). Use `PyJWT` for standard HMAC-SHA256 JWT generation and verification.

## ADR-004: Standard Error Response Format
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** PRD Rule 5 requires consistent JSON errors `{"error": {"code": str, "message": str}}` across all endpoints and status codes.
- **Decision:** Implement a global exception handler in FastAPI intercepting custom `AppException`, FastAPI's `RequestValidationError`, starlette's `HTTPException`, and uncaught `Exception` to guarantee the exact error envelope without leaking internal stack traces.

## ADR-005: Timezone Normalization (Asia/Kolkata) & Date Storage
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Target student cohort is in India (IST, UTC+05:30). Using naive UTC timestamps for daily study streaks and due-date cutoffs creates midnight boundary shifts and confusing scheduling.
- **Decision:** Use `Asia/Kolkata` as the canonical application timezone. `card_states.due_date` is stored as a pure SQL `Date` (calendar day). Centralize timezone access in `app.core.time` via `today_ist() -> date` and `now_ist() -> datetime` across all services, queries, and background tasks.

## ADR-006: Review Idempotency & Transaction Concurrency
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Mobile or poor network connections can cause duplicate review submissions from button spamming or retry logic, which would otherwise erroneously advance SM-2 intervals multiple times.
- **Decision:** Allow an optional client-generated `request_id` in `POST /api/reviews`. Use pessimistic row locking (`with_for_update` on PostgreSQL) during review submission. If a review with the same `request_id` was already processed for this card on the same day, return the current card state idempotently without mutating SM-2 state.

## ADR-007: Gemini LLM Client via REST API over HTTPX
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** PRD Section 4 specifies Google Gemini API behind an `LLMClient` interface with model configurable via `GEMINI_MODEL`. Heavy SDKs frequently incur breaking API changes, grpc compilation issues, and obscure HTTP retry control.
- **Decision:** Implement `GeminiLLMClient` adhering to `LLMClient` using standard `httpx.Client`. Connect directly to the Gemini REST API (`generateContent`) using `responseMimeType: "application/json"`. Implement custom backoff for 429 (respecting `Retry-After`), 5xx, timeouts, and JSON syntax errors up to 2 retries.

## ADR-008: Pluggable JobEventPublisher Hook for Live Generation
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Phase 3 requires the background generation pipeline to broadcast progress events, but WebSockets are strictly scoped to Phase 4.
- **Decision:** Introduce a `JobEventPublisher` protocol in `app.services.events` with methods `chunk_done`, `chunk_failed`, `ready`, and `failed`. Provide a default `NullJobEventPublisher` for Phase 3. In Phase 4, the WebSocket `ConnectionManager` broadcaster will seamlessly inject as the active publisher without modifying pipeline logic.

## ADR-009: Background Job Session Isolation and Startup Recovery Lifecycle
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Render free-tier instances sleep or restart intermittently, killing in-flight background tasks. Reusing request database sessions in background threads causes session state conflicts and leaks.
- **Decision:** All background tasks (`process_upload_pipeline`, `run_card_generation`) instantiate and manage their own isolated `SessionLocal()` database sessions. During FastAPI application startup (via `lifespan` context manager), any jobs stranded in `queued` or `processing` states are automatically updated to `status='failed'` with `error_message='Server restarted during processing'`. Users are restricted to a single active job at a time (`JOB_IN_PROGRESS` 409).

## ADR-010: Failed Upload Cleanup Strategy for Idempotent Retries
- **Date:** 2026-10-25
- **Status:** Accepted
- **Context:** Files are deduplicated per user by SHA-256 hash. If an earlier upload failed during LLM extraction leaving an empty deck (0 cards), subsequent uploads of the exact same document would otherwise be rejected with a 409 duplicate conflict, blocking the user from ever generating flashcards from that document.
- **Decision:** During `POST /api/uploads`, if an existing deck matches `(user_id, file_hash)` and has 0 cards (from a failed generation attempt), the system deletes the empty deck and allows the new upload and generation job to proceed normally.

## ADR-011: Database as Source of Truth & Live WebSocket Generation Protocol
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** Real-time generation streaming must be resilient to client disconnects, page reloads, and network dropouts, without tying background task completion to client connectivity or exhausting Neon connection pool limits.
- **Decision:**
  1. **DB as Single Source of Truth:** Generation jobs proceed and update the database independently of whether any WebSocket is connected. A frontend that reconnects or misses messages can always recover complete state via `GET /api/jobs/{id}` and `GET /api/decks/{id}/cards`.
  2. **Short DB Sessions:** The WebSocket endpoint `/ws/generate/{job_id}` opens a short-lived `SessionLocal()`, loads the user and job, builds the snapshot, and closes the session before entering the receive loop. Database sessions are never held open across the socket's lifetime to avoid depleting database connection pools.
  3. **Register-Before-Snapshot Ordering:** The socket is registered in the room (`connection_manager.connect`) *before* the snapshot is transmitted. This eliminates race conditions where live events generated immediately after connection could be dropped.
  4. **Frontend State Invariant:** Because a live event can arrive just before the snapshot, the frontend must adhere to the rule: "a snapshot must never move the UI backwards (ignore it if a terminal ready/failed event was already received)". Terminal events (ready/failed) delivered via both live broadcast and replay must be handled idempotently.

## ADR-012: Cross-Thread Broadcasting, Send Concurrency Safety & Query Token Privacy
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** Background generation tasks run in threadpool workers, while WebSocket I/O requires the main asyncio event loop. Concurrent writes from keepalive pings and broadcasts on the same socket can interleave frames. Furthermore, standard browser WebSocket APIs do not support custom HTTP headers on connection.
- **Decision:**
  1. **Thread-Safe Scheduling:** The FastAPI `lifespan` startup captures the main asyncio event loop via `asyncio.get_running_loop()`. `WebSocketJobEventPublisher` schedules broadcasts from worker threads onto the loop using `asyncio.run_coroutine_threadsafe()`. Sockets and publisher calls never block worker threads.
  2. **Per-Socket Lock & Timeout:** `ConnectionManager` maintains a dedicated `asyncio.Lock` per socket and bounds every transmission with `asyncio.wait_for(..., timeout=5)`. Stalled or disconnected sockets are automatically pruned without delaying or failing broadcasts to remaining participants.
  3. **Query Parameter Token Privacy:** Because browser WebSockets cannot send `Authorization: Bearer` headers, tokens are passed via `?token=...`. To prevent credentials leaking in server access logs or terminal logs, the uvicorn access logger and application loggers must never print unmasked query strings containing authentication tokens.

## ADR-013: Stats & Analytics Aggregation Strategy, 365-Day Streak Lookback & IST Midnight Bucketing
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** PRD Section 7.3 specifies analytics including consecutive review streak, 7-day review histogram, 30-day topic accuracy, 30-day review workload forecast, and expected retention on exam. Computing the streak from the 7-day query would artificially cap streaks at 7 days. Timezone shifts between UTC and IST (+05:30) can cause reviews performed near midnight to land on the wrong calendar date, and SQLite stores naive datetime strings whereas PostgreSQL stores TIMESTAMPTZ.
- **Decision:**
  1. **365-Day Single-Column Query for Streak & Histogram:** To prevent capping streaks at 7 days while avoiding unbounded scans, streak is computed using a bounded 365-day lookback on `Review.reviewed_at` for `current_user.id` (`select(Review.reviewed_at).where(...)`). The query fetches only that single indexed column. In Python, each timestamp is converted to its Asia/Kolkata date via `to_ist_date()`, and the consecutive day streak is calculated from the resulting date set. The 7-day histogram reuses the exact same 365-day query result in Python memory, eliminating a second database query and guaranteeing that streak and histogram agree on identical IST dates.
  2. **IST Midnight Window Starts & Naive SQLite Handling:** All date windows (7-day, 30-day, 365-day) start at Asia/Kolkata midnight (`00:00:00 IST`) of the start day (`ist_midnight()`). This guarantees consistency: a review within the last 30 calendar days at 09:00 IST is included in topic accuracy even if elapsed wall time exceeds 30x24 hours. Because `reviews.py` writes `now_ist()`, SQLite stores the naive IST wall-clock string without offset. `to_ist_date()` checks `val.tzinfo`: if naive, it treats the clock value as already IST wall time (`val.date()`), avoiding the 5h30m double-shift bug that would misattribute 23:50 IST reviews to the next calendar day. Tz-aware timestamps are converted using `.astimezone(IST_TIMEZONE).date()`.
  3. **Strict User Isolation in Topic Aggregation Joins:** Topic accuracy computes the share of ratings >= 3 over the last 30 IST days per topic across decks owned by the user. To prevent cross-user contamination when cards share identical topic names across different users or deck imports, the SQL query applies a filtered `LEFT JOIN` with `Review.card_id == Card.id AND Review.user_id == :uid AND Review.reviewed_at >= cutoff_30d`. Topics with 0 reviews return `accuracy: null, is_weak: false`.
  4. **Ebbinghaus Forgetting Curve Retention Approximation:** Expected retention on exam approximates recall probability using $R_i = \exp(-t_i / S_i)$, where $t_i = \max(0, (\text{exam\_date} - \text{last\_reviewed\_date\_ist}).\text{days})$ and $S_i = \max(\text{interval\_days}, 1)$. This represents an "if you stopped revising now" estimate of recall on exam day across reviewed cards. Cards with `last_reviewed_at is null` are excluded. If no reviewed cards exist or exam_date <= today, retention returns `null`. Accuracy and retention are rounded to 1 decimal place.
  5. **Overview Queue Size Alignment:** `/api/stats/overview` returns `queue_size_today = min(due_today, DAILY_CARD_LIMIT)` and `daily_limit` alongside `due_today`, ensuring the dashboard card count matches what the Review page will actually present to the user.

## ADR-014: Production Deployment Architecture, Neon Pool Limits & Single-Worker In-Memory State
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** Deploying on Render's free tier with Neon PostgreSQL requires accounting for limited connection pool sizes, reverse proxy forwarding headers, idle spin-downs, and real-time state synchronization.
- **Decision:**
  1. **Single-Worker Execution:** The Uvicorn server is launched with exactly one worker (no `--workers` flag) and flags `--proxy-headers --forwarded-allow-ips="*"`. This ensures that in-memory state—specifically the IP sliding-window rate limiters, WebSocket room connection sets (`ConnectionManager`), and upcoming Quiz Duel rooms—is consistent. Running multiple worker processes would partition in-memory memory spaces across isolated OS processes.
  2. **Neon PostgreSQL Pool Configuration:** To prevent exhausting connection quotas on Neon's free tier, the SQLAlchemy engine uses `pool_size=3`, `max_overflow=2`, and `pool_pre_ping=True`. URL normalization transparently rewrites `postgres://` and `postgresql://` schemes to `postgresql+psycopg2://`.
  3. **Strict CORS & WebSocket Origin Enforcement:** CORS credentials are set to `False` with explicit methods (`GET, POST, PATCH, DELETE, OPTIONS`) and headers (`Authorization, Content-Type`). Trailing slashes in `ALLOWED_ORIGINS` are stripped before matching. WebSocket connections validate the `Origin` header against `ALLOWED_ORIGINS` and terminate unauthorized origins with close code `4403`. Wildcards (`*`) are disallowed in production mode.
  4. **Health Check Split for Neon Idle Sleep:** `/health` is a pure in-memory endpoint with no database query, designated for external uptime pinging (e.g., UptimeRobot every 5 minutes). A separate `/health/db` endpoint executes `SELECT 1` for manual diagnostics. This prevents periodic health pings from indefinitely keeping the Neon compute instance awake.
  5. **Production Invariants Guard:** If `ENV=production`, the application refuses to boot if `DATABASE_URL` is empty or points to SQLite, if `JWT_SECRET` is the default dev secret or shorter than 32 characters, or if `ALLOWED_ORIGINS` contains wildcards.

## ADR-015: Frontend Token Storage in localStorage, SPA Routing & Cold Start Wake-Up UX
- **Date:** 2026-10-26
- **Status:** Accepted
- **Context:** The frontend is a Single Page Application (SPA) hosted on Vercel calling an independent FastAPI backend on Render. Authentication uses JWT tokens for both REST requests and WebSocket connections (`?token=...`). Render's free tier spins down on inactivity, resulting in 30-60 second latency on cold start requests.
- **Decision:**
  1. **Token Storage in localStorage:** Store the JWT token in `localStorage` under `recallos_token`.
     - *Trade-off / Security Analysis:* `localStorage` is accessible to JavaScript running within the application's origin, making it theoretically vulnerable to Cross-Site Scripting (XSS) if untrusted scripts run. However, an `httpOnly` cookie strategy across cross-site domains (Vercel at `*.vercel.app` and Render at `*.onrender.com`) introduces third-party cookie blocking, complex SameSite/Secure policies, and cannot be accessed by standard browser `WebSocket` APIs to attach query parameters. Given the 2-day student project scope, zero third-party dependencies with user-rendered script injection, and cross-origin WebSocket requirements, `localStorage` provides reliable, predictable authentication. Tokens are never logged to the browser console.
  2. **Render Cold-Start UX & In-Flight Tracking:**
     - The HTTP client tracks in-flight request count and arms a 4-second timer per request. If any request exceeds 4 seconds, a global sticky wake-up banner appears: *"Server is waking up, this can take up to a minute..."*.
     - The client timeout is configured to 90 seconds (preventing early client abortion while Render spins up).
     - For idempotent `GET` requests, the client automatically retries up to 3 times with 3-second delays when encountering network disconnects or 502/503 bad gateway responses from the booting reverse proxy. `POST/PATCH/DELETE` requests are never automatically retried, except `POST /api/reviews` which carries a client-generated UUID `request_id` for backend idempotency.
  3. **Vercel SPA Rewrites:** `frontend/vercel.json` configures a global rewrite `{"source": "/(.*)", "destination": "/index.html"}`. Because Vercel serves static assets prior to applying route rewrites, this guarantees deep-link navigation (e.g., direct refreshes on `/review` or `/decks`) resolves correctly to the SPA router.

