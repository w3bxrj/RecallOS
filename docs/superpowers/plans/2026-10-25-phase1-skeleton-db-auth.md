# Phase 1 Implementation Plan - Skeleton, DB & Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up RecallOS repository structure, FastAPI backend app with env config, all 7 SQLAlchemy models, Alembic migrations, standard error handling, native bcrypt + PyJWT auth endpoints, and pytest tests.

**Architecture:** Greenfield modular FastAPI backend with SQLAlchemy 2.0 ORM models using portable types (PostgreSQL for dev/prod, SQLite for pytest), native bcrypt password hashing with strict 72-byte guardrails, PyJWT authentication, and a centralized JSON error envelope.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, psycopg2-binary, bcrypt, PyJWT, pydantic-settings, pytest, httpx.

**Spec:** docs/superpowers/specs/2026-10-25-phase1-skeleton-db-auth-design.md

## Global Constraints
- Target Python 3.13 with pinned versions in `backend/requirements.txt`.
- All secret keys live in `.env` (git-ignored) with zero defaults for production secrets; maintain `.env.example`.
- Generic portable database types only (no PostgreSQL-only dialect types, standard `JSON` for distractors).
- Every endpoint returns `{"error": {"code": str, "message": str}}` on error with appropriate HTTP status code.
- Passwords must be at least 8 characters and at most 72 bytes (UTF-8).
- `password_hash` must never be serialized or returned in any API response.
- Small, conventional commits for each task.

## Review Focus
- Passwords exceeding 72 UTF-8 bytes must be rejected with 400 `PASSWORD_TOO_LONG`.
- Duplicate email registration must return 409 `EMAIL_EXISTS`.
- Invalid credentials or nonexistent email on login must return 401 `INVALID_CREDENTIALS`.
- Expired or malformed JWT token must return 401 `INVALID_TOKEN`.
- Validation errors must return 422 with the standardized `{"error": {"code": "VALIDATION_ERROR", ...}}` format.

---

### Task 1: Repository Scaffolding, Git Init, Dependencies & Environment Setup

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`

**Interfaces:**
- Produces: Base repository structure and dependency manifest.

- [ ] **Step 1: Initialize git repository**
Run: `git init`

- [ ] **Step 2: Create `.gitignore` and `.env.example`**
Ensure `.env`, `__pycache__`, `venv`, `.pytest_cache`, `*.db` are ignored.
`.env.example` contains:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/recallos
JWT_SECRET=replace-with-a-secure-random-secret
JWT_EXPIRE_MINUTES=1440
GEMINI_API_KEY=your-gemini-api-key
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
MAX_UPLOAD_MB=10
DAILY_CARD_LIMIT=50
```

- [ ] **Step 3: Create `backend/requirements.txt` with pinned versions**
FastAPI, Uvicorn, SQLAlchemy, Alembic, psycopg2-binary, bcrypt, PyJWT, pydantic, pydantic-settings, pytest, httpx.

- [ ] **Step 4: Verify virtual environment and install dependencies**
Run: `python -m venv backend/venv` and activate/install requirements.
Verify `pytest` and `uvicorn` run cleanly.

- [ ] **Step 5: Commit**
```bash
git add .gitignore .env.example backend/requirements.txt backend/app/__init__.py docs/
git commit -m "chore: scaffold repo structure, gitignore, and backend requirements"
```

---

### Task 2: Core Configuration, Database Engine & Standard Error Handling

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/db.py`
- Create: `backend/app/core/errors.py`
- Create: `backend/app/main.py`
- Create: `backend/app/schemas/error.py`

**Interfaces:**
- Produces: `settings` from `config.py`, `get_db` and `engine` from `db.py`, `AppException` and exception handlers in `errors.py`.

- [ ] **Step 1: Implement `backend/app/core/config.py`**
Use `pydantic_settings.BaseSettings` loading from `.env`. Provide sensible defaults for local dev / testing (`sqlite:///./dev.db`).

- [ ] **Step 2: Implement `backend/app/core/db.py`**
SQLAlchemy 2.0 engine and session factory `SessionLocal` with `get_db` dependency yielding sessions.

- [ ] **Step 3: Implement `backend/app/core/errors.py` and `backend/app/schemas/error.py`**
Standard error response model `{"error": {"code": str, "message": str}}`.
Custom exception `AppException(status_code: int, code: str, message: str)`.
Exception handlers for `AppException`, `RequestValidationError`, `HTTPException`, and generic `Exception`.

- [ ] **Step 4: Implement `backend/app/main.py` with health check and error handlers**
Expose `GET /api/health` returning `{"status": "ok"}`. Attach CORS middleware and global exception handlers.

- [ ] **Step 5: Verify main app startup and health check**
Run: `python -m uvicorn app.main:app --port 8000` (or test with httpx/curl).

- [ ] **Step 6: Commit**
```bash
git add backend/app/core backend/app/schemas backend/app/main.py
git commit -m "feat(core): add app configuration, database engine, and error handling framework"
```

---

### Task 3: SQLAlchemy Models for All Core Entities

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/deck.py`
- Create: `backend/app/models/job.py`
- Create: `backend/app/models/card.py`
- Create: `backend/app/models/card_state.py`
- Create: `backend/app/models/review.py`
- Create: `backend/app/models/duel.py`
- Create: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Base`, `User`, `Deck`, `Job`, `Card`, `CardState`, `Review`, `Duel`.

- [ ] **Step 1: Implement `backend/app/models/base.py`**
`class Base(DeclarativeBase): pass`

- [ ] **Step 2: Implement all 7 models conforming to PRD Section 6**
- `User`: `email` (unique, indexed), `password_hash`, `display_name`, `exam_date`, `created_at`.
- `Deck`: `user_id`, `title`, `source_filename`, `file_hash`, `created_at`, UniqueConstraint(`user_id`, `file_hash`).
- `Job`: `user_id`, `deck_id`, `status`, `total_chunks`, `done_chunks`, `cards_created`, `error_message`, `created_at`, `finished_at`.
- `Card`: `deck_id`, `topic`, `question`, `answer`, `distractors` (JSON), `created_at`.
- `CardState`: `card_id` (unique), `user_id`, `ease_factor` (default 2.5), `interval_days`, `repetitions`, `due_date`, `last_reviewed_at`, `lapses`, Index on (`user_id`, `due_date`).
- `Review`: `user_id`, `card_id`, `rating`, `reviewed_at`, `prev_interval`, `new_interval`, Index on (`user_id`, `reviewed_at`).
- `Duel`: `room_code` (unique), `deck_id`, `host_id`, `guest_id`, `status`, `host_score`, `guest_score`, `winner_id`, `created_at`, `finished_at`.

- [ ] **Step 3: Export all models in `backend/app/models/__init__.py`**

- [ ] **Step 4: Verify models metadata loads cleanly**
Run test script creating all tables in SQLite memory engine.

- [ ] **Step 5: Commit**
```bash
git add backend/app/models
git commit -m "feat(models): add SQLAlchemy 2.0 models for all core entities"
```

---

### Task 4: Alembic Configuration & Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/` (initial migration)

**Interfaces:**
- Consumes: `Base.metadata` from `app.models`.
- Produces: Versioned schema migration for PostgreSQL and SQLite.

- [ ] **Step 1: Initialize and configure Alembic**
Set `target_metadata = Base.metadata` in `alembic/env.py`. Configure connection string to read from `app.core.config.settings.DATABASE_URL`.

- [ ] **Step 2: Generate initial migration**
Run: `alembic revision --autogenerate -m "initial_schema"` in `backend`.

- [ ] **Step 3: Verify migration upgrade on SQLite and verify script syntax**
Run: `alembic upgrade head`.

- [ ] **Step 4: Commit**
```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat(db): configure alembic and generate initial database migration"
```

---

### Task 5: Security Utilities & Auth Pydantic Schemas

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/user.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`, `create_access_token(user_id: int) -> str`, `decode_access_token(token: str) -> int`.
- Produces: `UserRegisterRequest`, `UserLoginRequest`, `TokenResponse`, `UserResponse`, `UserUpdateRequest`.

- [ ] **Step 1: Implement `backend/app/core/security.py`**
- Validate password length <= 72 bytes (UTF-8). If > 72, raise `AppException(400, "PASSWORD_TOO_LONG", "Password must not exceed 72 bytes")`.
- `bcrypt.hashpw` and `bcrypt.checkpw`.
- `create_access_token` and `decode_access_token` with `PyJWT` and expiration time.

- [ ] **Step 2: Implement Pydantic schemas in `schemas/auth.py` and `schemas/user.py`**
- `UserRegisterRequest`: email (EmailStr), password (min_length=8), display_name (min_length=1).
- `UserLoginRequest`: email, password.
- `TokenResponse`: access_token, token_type="bearer".
- `UserResponse`: id, email, display_name, exam_date, created_at. (NO password_hash).
- `UserUpdateRequest`: display_name (optional), exam_date (optional).

- [ ] **Step 3: Unit test security utilities**
Run isolated test on password hashing, 72-byte limit, token creation and decoding.

- [ ] **Step 4: Commit**
```bash
git add backend/app/core/security.py backend/app/schemas
git commit -m "feat(auth): implement security utilities and auth schemas"
```

---

### Task 6: Authentication & User Routers (`/api/auth`, `/api/me`)

**Files:**
- Create: `backend/app/routers/auth.py`
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces:
  - `POST /api/auth/register` -> `UserResponse`
  - `POST /api/auth/login` -> `TokenResponse`
  - `GET /api/me` -> `UserResponse`
  - `PATCH /api/me` -> `UserResponse`
- Dependency: `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User`

- [ ] **Step 1: Implement `get_current_user` dependency**
Extract Bearer token, decode sub (user_id), query database. Raise 401 `INVALID_TOKEN` or `USER_NOT_FOUND`.

- [ ] **Step 2: Implement `routers/auth.py`**
- `register`: check email uniqueness. If exists, raise 409 `EMAIL_EXISTS`. Hash password and insert user. Return 201 with `UserResponse`.
- `login`: query user by email. If not found or `verify_password` fails, raise 401 `INVALID_CREDENTIALS`. Return 200 with `TokenResponse`.

- [ ] **Step 3: Implement `routers/users.py`**
- `GET /api/me`: return current user.
- `PATCH /api/me`: update `display_name` and/or `exam_date`. Return updated `UserResponse`.

- [ ] **Step 4: Register routers in `main.py`**
Include routers under `/api`.

- [ ] **Step 5: Commit**
```bash
git add backend/app/routers backend/app/main.py
git commit -m "feat(auth): add register, login, and me endpoints"
```

---

### Task 7: Pytest Integration Test Suite & Verification

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`

**Interfaces:**
- Fixtures: `db_session` (SQLite in-memory test DB), `client` (FastAPI TestClient with overridden `get_db`).

- [ ] **Step 1: Implement `backend/tests/conftest.py`**
Set up in-memory SQLite engine and test client fixture.

- [ ] **Step 2: Implement tests in `backend/tests/test_auth.py`**
- `test_register_success`: Valid user registration returns 201 and UserResponse without password_hash.
- `test_register_duplicate_email`: Duplicate registration returns 409 and code `EMAIL_EXISTS`.
- `test_register_password_too_long`: Password > 72 bytes returns 400 and code `PASSWORD_TOO_LONG`.
- `test_register_password_too_short`: Password < 8 characters returns 422 `VALIDATION_ERROR`.
- `test_login_success`: Valid login returns 200 and access_token.
- `test_login_wrong_password`: Invalid password returns 401 and code `INVALID_CREDENTIALS`.
- `test_login_nonexistent_email`: Unknown email returns 401 and code `INVALID_CREDENTIALS`.
- `test_me_authenticated`: Valid token allows `GET /api/me` and `PATCH /api/me`.
- `test_me_unauthenticated`: Request without token returns 401 `INVALID_TOKEN`.

- [ ] **Step 3: Run pytest test suite and ensure 100% pass rate**
Run: `pytest backend/tests -v`

- [ ] **Step 4: PostgreSQL migration validation**
Verify migration file compatibility against PostgreSQL syntax and run validation test.

- [ ] **Step 5: Commit**
```bash
git add backend/tests
git commit -m "test(auth): add comprehensive integration tests for auth and user endpoints"
```
