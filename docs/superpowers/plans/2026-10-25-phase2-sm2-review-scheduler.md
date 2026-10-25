# Phase 2 Implementation Plan - SM-2, Review Engine & Scheduler

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pure-function SM-2 scheduling algorithm, Asia/Kolkata timezone support, exam-mode capping/prioritization, review queue and submission endpoints, seed data script, and unit/integration tests.

**Architecture:** Pure function calculation layer (`services/sm2.py`) decoupled from database models; exam-mode prioritization and boundary capping (`services/scheduler.py`); concurrency-safe and idempotent API routers (`routers/reviews.py`).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic, pytest, zoneinfo.

**Spec:** docs/superpowers/specs/2026-10-25-phase2-sm2-review-scheduler-design.md

## Global Constraints
- Pure functions only in `services/sm2.py` (no DB access, review_date passed explicitly).
- Timezone is strictly `Asia/Kolkata` for `today_ist()` and `due_date` comparisons.
- `due_date` is stored as an SQL `Date`.
- `POST /api/reviews` runs in a single transaction with row locking and checks ownership.
- Small, conventional commits for each logical piece.

## Review Focus
- First review Good -> interval 1; second -> 6; third -> round(6 * EF).
- Again resets repetitions to 0, interval to 1, increments lapses.
- EF never drops below 1.3.
- Exam mode caps due date to `exam_date - 1 day`, but never earlier than tomorrow.
- Exam date in the past, today, or tomorrow defaults gracefully to tomorrow.
- Topic accuracy neutral (0.5) when reviews < 5.
- Idempotent review submission with duplicate `request_id`.
- User B cannot review user A's card (returns 404).

---

### Task 1: Timezone Helpers, Model Updates & Alembic Migration

**Files:**
- Create: `backend/app/core/time.py`
- Modify: `backend/app/models/card_state.py`
- Modify: `backend/app/models/review.py`
- Create: `backend/alembic/versions/` (migration for Date type and request_id)

- [ ] **Step 1: Implement `backend/app/core/time.py`**
Provide `now_ist() -> datetime` and `today_ist() -> date` using `zoneinfo.ZoneInfo("Asia/Kolkata")`.

- [ ] **Step 2: Update `card_state.py` and `review.py`**
Change `due_date` from `DateTime` to `Date` in `CardState`. Add optional `request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)` to `Review`.

- [ ] **Step 3: Generate and run Alembic migration**
Generate migration and run `alembic upgrade head`.

- [ ] **Step 4: Commit**
```bash
git add backend/app/core/time.py backend/app/models/ backend/alembic/
git commit -m "feat(db): update due_date to SQL Date and add IST timezone helpers"
```

---

### Task 2: Pure SM-2 Spaced Repetition Engine & Unit Tests

**Files:**
- Create: `backend/app/services/sm2.py`
- Create: `backend/tests/test_sm2.py`

- [ ] **Step 1: Write failing unit tests in `tests/test_sm2.py`**
Test:
- First review Good (rating 3) -> interval 1, repetitions 1
- Second review Good -> interval 6, repetitions 2
- Third review Good -> interval round(6 * 2.5) = 15, repetitions 3
- Again (rating 1) -> repetitions 0, interval 1, lapses incremented
- Easy (rating 4) -> EF increases
- Hard (rating 2) -> EF decreases
- Minimum EF floor -> EF cannot drop below 1.3

- [ ] **Step 2: Implement `app/services/sm2.py`**
Implement `SM2Result` dataclass and pure `calculate_sm2`.

- [ ] **Step 3: Run pytest to verify all tests pass**
Run: `pytest tests/test_sm2.py -v`

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/sm2.py backend/tests/test_sm2.py
git commit -m "feat(sm2): implement pure SM-2 calculation engine and unit tests"
```

---

### Task 3: Scheduler, Exam-Mode Capping & Queue Prioritization

**Files:**
- Create: `backend/app/services/scheduler.py`
- Create: `backend/tests/test_exam_mode.py`

- [ ] **Step 1: Write failing unit tests in `tests/test_exam_mode.py`**
Test:
- Due date capping: future exam date caps interval to `exam_date - 1 day`
- Edge cases: exam date tomorrow, exam date today, exam date in past -> capped to tomorrow
- Priority formula with weak topics and overdue cards
- Neutral topic accuracy (0.5) when review count < 5

- [ ] **Step 2: Implement `app/services/scheduler.py`**
Implement `apply_exam_mode_cap` and `calculate_card_priority`.

- [ ] **Step 3: Run pytest to verify tests pass**
Run: `pytest tests/test_exam_mode.py -v`

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/scheduler.py backend/tests/test_exam_mode.py
git commit -m "feat(scheduler): implement exam-mode interval capping and queue prioritization"
```

---

### Task 4: Review Queue Endpoint (`GET /api/reviews/queue`)

**Files:**
- Create: `backend/app/schemas/review.py`
- Create: `backend/app/routers/reviews.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Implement Pydantic schemas in `schemas/review.py`**
`QueueCardResponse` (card details + predicted intervals for 4 ratings), `QueueResponse` (cards list, total_due, remaining_count).

- [ ] **Step 2: Implement queue query in `routers/reviews.py`**
Query due cards for current user (`due_date <= today_ist()`), apply exam mode sorting or due_date sorting, paginate by `DAILY_CARD_LIMIT`, calculate predicted intervals.

- [ ] **Step 3: Register router in `main.py`**

- [ ] **Step 4: Commit**
```bash
git add backend/app/schemas/review.py backend/app/routers/reviews.py backend/app/main.py
git commit -m "feat(reviews): add review queue endpoint with interval prediction"
```

---

### Task 5: Review Submission Endpoint (`POST /api/reviews`)

**Files:**
- Modify: `backend/app/routers/reviews.py`
- Modify: `backend/app/schemas/review.py`

- [ ] **Step 1: Implement review submission with row locking and idempotency**
Accept `card_id`, `rating` (1..4), optional `request_id`.
Verify user owns the deck/card (404 if not found).
Lock card_state row, check if `request_id` duplicate today.
Calculate SM-2, apply exam-mode cap if user has exam_date, update `CardState`, insert `Review`.

- [ ] **Step 2: Commit**
```bash
git add backend/app/routers/reviews.py backend/app/schemas/review.py
git commit -m "feat(reviews): implement atomic review submission with double-submission protection"
```

---

### Task 6: Seed Script (`scripts/seed.py`)

**Files:**
- Create: `backend/scripts/seed.py`

- [ ] **Step 1: Implement `scripts/seed.py`**
Verify environment != "production".
Create test user `testuser@example.com`, deck of 30 cards across 4 topics (Networks, OS, DBMS, System Design).
Seed varied `due_date`s (overdue, today, upcoming).

- [ ] **Step 2: Test run seed script**
Run: `python scripts/seed.py`

- [ ] **Step 3: Commit**
```bash
git add backend/scripts/seed.py
git commit -m "chore(seed): add database seeding script with sample decks and cards"
```

---

### Task 7: Comprehensive Integration Tests & Verification

**Files:**
- Create: `backend/tests/test_reviews.py`

- [ ] **Step 1: Implement integration tests in `tests/test_reviews.py`**
Test:
- Queue retrieval with predicted intervals
- Exam mode reordering vs default due date ordering
- Review submission updates card state and records review
- User B cannot review User A's card (returns 404)
- Duplicate `request_id` does not re-apply SM-2

- [ ] **Step 2: Run all backend tests and confirm 100% pass rate**
Run: `pytest tests -v`

- [ ] **Step 3: Commit**
```bash
git add backend/tests/test_reviews.py
git commit -m "test(reviews): add integration tests for review queue, ownership, and idempotency"
```
