# RecallOS Phase 1 Design Specification: Skeleton, DB & Auth

## 1. Overview & Scope
Phase 1 establishes the RecallOS backend foundation:
- Repository structure matching PRD.md Section 13.
- Python backend using FastAPI, Pydantic-settings, and Uvicorn.
- SQLAlchemy 2.x declarative models for all 7 tables in PRD.md Section 6 with portable types (SQLite for testing, PostgreSQL for dev/prod).
- Alembic database migration setup and initial migration.
- Error handling framework: consistent `{"error": {"code": str, "message": str}}` schema and global exception handlers.
- Auth system: password hashing using `bcrypt` (enforcing max 72 bytes constraint), JWT token generation/verification using `PyJWT`.
- Endpoints: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/me`, `PATCH /api/me`.
- Pytest test suite testing registration, login, invalid credentials, and duplicate registration.
- Documentation: `docs/DECISIONS.md`, `.env.example`, `.gitignore`.

## 2. Directory Structure
```text
recallos/
  PRD.md
  README.md
  docs/
    DECISIONS.md
    superpowers/
      specs/
      plans/
  .env.example
  .gitignore
  backend/
    requirements.txt
    alembic.ini
    alembic/
      env.py
      script.py.mako
      versions/
    app/
      __init__.py
      main.py
      core/
        __init__.py
        config.py
        db.py
        security.py
        errors.py
      models/
        __init__.py
        base.py
        user.py
        deck.py
        job.py
        card.py
        card_state.py
        review.py
        duel.py
      schemas/
        __init__.py
        auth.py
        user.py
        error.py
      routers/
        __init__.py
        auth.py
        users.py
    tests/
      __init__.py
      conftest.py
      test_auth.py
```

## 3. Data Models Specification (SQLAlchemy 2.x)
All models inherit from `Base` (`DeclarativeBase`).
Portable types: `Integer`, `String`, `Text`, `Boolean`, `DateTime`, `Float`, `JSON`.

1. **User (`users`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `email`: String(255), unique=True, nullable=False, index=True
   - `password_hash`: String(255), nullable=False
   - `display_name`: String(100), nullable=False
   - `exam_date`: DateTime(timezone=True), nullable=True
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False

2. **Deck (`decks`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `user_id`: Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
   - `title`: String(255), nullable=False
   - `source_filename`: String(255), nullable=False
   - `file_hash`: String(64), nullable=False
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False
   - Constraint: `UniqueConstraint("user_id", "file_hash", name="uq_deck_user_file_hash")`

3. **Job (`jobs`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `user_id`: Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
   - `deck_id`: Integer, ForeignKey("decks.id", ondelete="SET NULL"), nullable=True
   - `status`: String(50), nullable=False, default="queued"  # queued, processing, ready, failed
   - `total_chunks`: Integer, default=0, nullable=False
   - `done_chunks`: Integer, default=0, nullable=False
   - `cards_created`: Integer, default=0, nullable=False
   - `error_message`: Text, nullable=True
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False
   - `finished_at`: DateTime(timezone=True), nullable=True

4. **Card (`cards`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `deck_id`: Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True
   - `topic`: String(255), nullable=False, index=True
   - `question`: Text, nullable=False
   - `answer`: Text, nullable=False
   - `distractors`: JSON, nullable=False  # list of 3 strings
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False

5. **CardState (`card_states`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `card_id`: Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
   - `user_id`: Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
   - `ease_factor`: Float, default=2.5, nullable=False
   - `interval_days`: Integer, default=0, nullable=False
   - `repetitions`: Integer, default=0, nullable=False
   - `due_date`: DateTime(timezone=True), nullable=False
   - `last_reviewed_at`: DateTime(timezone=True), nullable=True
   - `lapses`: Integer, default=0, nullable=False
   - Index: `Index("ix_card_states_user_due_date", "user_id", "due_date")`

6. **Review (`reviews`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `user_id`: Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
   - `card_id`: Integer, ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True
   - `rating`: Integer, nullable=False  # 1, 2, 3, 4
   - `reviewed_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False
   - `prev_interval`: Integer, nullable=False
   - `new_interval`: Integer, nullable=False
   - Index: `Index("ix_reviews_user_reviewed_at", "user_id", "reviewed_at")`

7. **Duel (`duels`)**:
   - `id`: Integer, primary_key=True, autoincrement=True
   - `room_code`: String(10), unique=True, nullable=False, index=True
   - `deck_id`: Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False
   - `host_id`: Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
   - `guest_id`: Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
   - `status`: String(50), nullable=False, default="waiting"  # waiting, active, finished, abandoned
   - `host_score`: Integer, default=0, nullable=False
   - `guest_score`: Integer, default=0, nullable=False
   - `winner_id`: Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
   - `created_at`: DateTime(timezone=True), default=datetime.utcnow, nullable=False
   - `finished_at`: DateTime(timezone=True), nullable=True

## 4. Error Response Format
All errors return HTTP status code with body:
```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human readable message"
  }
}
```
Global exception handlers:
- `AppException` (custom base exception with status_code, code, message)
- `RequestValidationError` -> 422 with code `"VALIDATION_ERROR"`
- `HTTPException` -> preserves status_code with code `"HTTP_ERROR"` or mapped code
- `Exception` -> 500 with code `"INTERNAL_SERVER_ERROR"`, logs error without leaking stack trace

## 5. Security & Authentication
- Password hashing: `bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")`.
- If password exceeds 72 UTF-8 bytes, reject with 400 `"PASSWORD_TOO_LONG"`.
- Password verification: `bcrypt.checkpw(password.encode("utf-8")[:72], hash.encode("utf-8"))`.
- Token: `jwt.encode({"sub": str(user.id), "exp": exp}, secret, algorithm="HS256")`.
- `get_current_user` FastAPI dependency extracts and validates Bearer token, fetches user from DB, raising 401 if missing or invalid.
- Never expose `password_hash` in schemas or API outputs.
