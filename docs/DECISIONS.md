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

