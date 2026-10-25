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
