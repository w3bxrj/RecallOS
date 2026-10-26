# Phase 5: Stats & Analytics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5: Stats & Analytics API (`GET /api/stats/overview`, `GET /api/stats/topics`, `GET /api/stats/forecast`), pure retention and streak calculation functions, IST date/boundary conversion helpers, and realistic historical review data in `seed.py`.

**Architecture:** Pure algorithmic functions in `services/stats.py` handle Ebbinghaus retention estimation and continuous streak evaluation. Date bucketing and window boundaries use Asia/Kolkata (IST) midnight conventions in `core/time.py`. Database aggregations use SQL `GROUP BY` and filtered `LEFT JOIN` scoped strictly to `current_user.id`. The overview endpoint reuses a single 365-day `reviewed_at` query for both the 365-day streak and the 7-day histogram to avoid redundant queries.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Python 3.13 `zoneinfo` / `datetime`, Pytest.

**Spec:** PRD Sections 7.3 & 8, and user approved design changes.

## Global Constraints

- Scoped strictly to `current_user.id` on all endpoints and queries. User A must never see User B's statistics, reviews, or forecast (no N+1 queries).
- All date calculations and midnight windows use `today_ist()` / Asia/Kolkata (+05:30).
- Topic accuracy = share of reviews with rating >= 3 over the last 30 IST days per topic (rounded to 1 decimal). `is_weak = accuracy < 60.0 AND reviews_count >= 5`.
- Overview provides `queue_size_today = min(due_today, DAILY_CARD_LIMIT)` and `daily_limit` to match the Review page.
- Streak is computed over a 365-day lookback from `Review.reviewed_at` timestamps converted to IST dates in Python, preventing any 7-day cap.
- Seed script must only use existing 4 topics (`Computer Networks`, `Operating Systems`, `Database Management`, `System Design`), set `last_reviewed_at` and `interval_days` on card_states, feature at least 9 consecutive review days ending today, and refuse to run if `ENV=production`.
- Retention calculation docstring and DECISIONS.md explicitly document that expected retention on exam is an "if you stopped revising now" estimate based on the Ebbinghaus forgetting curve.

## Review Focus

1. **Streak Lookback Cap:** Streak is computed using a 365-day lookback, verified by a test with a 10-day streak to prove it is not capped at 7. The 7-day histogram and streak agree on the same IST dates.
2. **IST Midnight Boundaries:** Boundary reviews at 23:50 IST and 00:10 IST land on different calendar days; reviews on the 30th day at 09:00 IST are included in the 30-day window starting at IST midnight even if >720 hours ago.
3. **User Isolation on Every Query:** No cross-user leakage. `LEFT JOIN reviews` in topic aggregation includes `AND r.user_id = :uid` so another user's review on a shared card never corrupts topic accuracy.
4. **No N+1 Queries:** Overview, topics, and forecast use set-based aggregation queries (`GROUP BY` and SQL joins).
5. **Retention Curve Approximation:** `exp(-t / S)` correctly handles cards with `last_reviewed_at is not None`, converting `last_reviewed_at` to IST date before computing `t`, skipping null rows, clamped `t >= 0`, `S >= 1`, and returns `None` when no reviewed cards exist or exam is in the past. Docstring explicitly notes it is an "if you stopped revising now" estimate.
6. **Topic Sorting Stability:** Weak topics (`is_weak=True`) appear first, then sorted by accuracy ascending, with unreviewed topics (`accuracy=None`) appearing last.

---

### Task 1: Time Helpers & Pure Stats Functions

**Files:**
- Modify: `backend/app/core/time.py`
- Create: `backend/app/services/stats.py`
- Create: `backend/tests/test_stats.py`

**Interfaces:**
- Produces in `app.core.time`:
  - `ist_midnight(d: date) -> datetime`: returns `datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=IST_TIMEZONE)`.
  - `to_ist_date(val: Optional[Union[datetime, date]]) -> Optional[date]`: handles tz-aware and naive IST datetime from SQLite without double-shifting.
- Produces in `app.services.stats`:
  - `calculate_expected_retention(cards_data: List[Tuple[Optional[date], int]], exam_date: Optional[date], current_date: date) -> Optional[float]`
  - `calculate_streak(review_dates: Set[date], today: date) -> int`

- [ ] **Step 1: Write unit tests in `backend/tests/test_stats.py`**
  - Test `to_ist_date` with tz-aware UTC, tz-aware IST, naive IST from SQLite, and date objects.
  - Test `ist_midnight` boundary comparisons (23:50 IST vs 00:10 IST on next day; 30-day midnight boundary).
  - Test `calculate_streak`:
    - 0 reviews -> 0 streak.
    - Review today only -> 1 streak.
    - Review yesterday only -> 1 streak.
    - Review 2 days ago only -> 0 streak.
    - 10-day continuous streak ending today -> 10.
    - 10-day continuous streak ending yesterday -> 10.
    - Broken streak (gap 2 days ago) -> 1.
  - Test `calculate_expected_retention`:
    - Hand-calculated example with 2 cards.
    - `exam_date is None` -> returns `None`.
    - `exam_date <= current_date` -> returns `None`.
    - No reviewed cards (`len(cards_data) == 0` or all `last_reviewed_date is None`) -> returns `None`.

- [ ] **Step 2: Run tests to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_stats.py -v`
  Expected: FAIL (module `app.services.stats` not found).

- [ ] **Step 3: Implement `time.py` updates and `services/stats.py`**
  - Update `to_ist_date` in `backend/app/core/time.py` so naive datetimes are treated as IST wall clock time (`val.date()`).
  - Add `ist_midnight(d: date) -> datetime` in `backend/app/core/time.py`.
  - Implement `calculate_expected_retention` in `backend/app/services/stats.py`: docstring must explicitly state that this is an "if you stopped revising now" estimate based on the Ebbinghaus forgetting curve.
  - Implement `calculate_streak` in `backend/app/services/stats.py`.

- [ ] **Step 4: Run tests to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_stats.py -k "test_to_ist_date or test_ist_midnight or test_calculate" -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/core/time.py backend/app/services/stats.py backend/tests/test_stats.py
  git commit -m "feat(stats): implement retention and streak calculation service with IST helpers and unit tests"
  ```

---

### Task 2: Stats Schemas and Endpoints

**Files:**
- Create: `backend/app/schemas/stats.py`
- Create: `backend/app/routers/stats.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Produces schemas in `app.schemas.stats`:
  - `DailyReviewCount`: `{ date: str, count: int }`
  - `StatsOverviewResponse`: `{ due_today: int, queue_size_today: int, daily_limit: int, total_cards: int, reviews_last_7_days: List[DailyReviewCount], streak_days: int, expected_retention_on_exam: Optional[float], exam_date: Optional[date], days_to_exam: Optional[int] }`
  - `TopicAccuracyItem`: `{ topic: str, accuracy: Optional[float], reviews_count: int, is_weak: bool }`
  - `ForecastItem`: `{ date: str, due_count: int }`
  - `ForecastResponse`: `{ forecast: List[ForecastItem] }`
- Produces endpoints in `app.routers.stats`:
  - `GET /stats/overview`
  - `GET /stats/topics`
  - `GET /stats/forecast`

- [ ] **Step 1: Write integration tests in `backend/tests/test_stats.py`**
  - Test `GET /api/stats/overview` returns all expected fields including `queue_size_today` and `daily_limit`.
  - Test 10-day streak in `overview` endpoint returns `streak_days == 10`.
  - Test `GET /api/stats/topics`:
    - Topic with 4 reviews <60% is `is_weak=False`.
    - Topic with 5 reviews <60% is `is_weak=True`.
    - Weak topics appear first, sorted by accuracy ascending, unreviewed topics last.
  - Test `GET /api/stats/forecast`:
    - Exactly 30 entries starting from `today_ist()`.
    - Overdue cards folded into day 0.

- [ ] **Step 2: Run tests to verify failure**
  Run: `venv\Scripts\pytest backend/tests/test_stats.py -k "test_api_stats" -v`
  Expected: FAIL (404 Not Found).

- [ ] **Step 3: Implement `schemas/stats.py`, `routers/stats.py`, and register in `main.py`**
  - Implement Pydantic models in `app/schemas/stats.py`.
  - Implement `get_stats_overview`:
    - Query 365-day reviews for `current_user.id`, convert to IST dates, build streak & 7-day histogram.
    - Query `due_today`, `queue_size_today = min(due_today, settings.DAILY_CARD_LIMIT)`, `daily_limit`.
    - Query `total_cards` across user's decks.
    - If `exam_date > today`, query reviewed cards' `last_reviewed_at` and `interval_days` (skipping null rows), convert `last_reviewed_at` to IST date before computing, and call `calculate_expected_retention`.
  - Implement `get_stats_topics`:
    - Query user decks joined with cards, left-joined with reviews (`AND r.user_id = current_user.id AND r.reviewed_at >= cutoff_30d`).
    - Compute `accuracy = round((good / count) * 100.0, 1)` and `is_weak = count >= 5 and accuracy < 60.0`.
    - Sort weak topics first, lowest accuracy first, nulls last.
  - Implement `get_stats_forecast`:
    - Aggregate card counts grouped by `due_date`.
    - Fold overdue cards (`due_date <= today`) into day 0.
    - Exactly 30 entries from `today` to `today + 29 days`.
  - Register `stats.router` in `backend/app/main.py` under `/api`.

- [ ] **Step 4: Run tests to verify PASS**
  Run: `venv\Scripts\pytest backend/tests/test_stats.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/schemas/stats.py backend/app/routers/stats.py backend/app/main.py backend/tests/test_stats.py
  git commit -m "feat(api): implement stats overview, topics, and forecast endpoints"
  ```

---

### Task 3: Comprehensive User Isolation and Edge Case Tests

**Files:**
- Modify: `backend/tests/test_stats.py`

**Interfaces:**
- Consumes: All stats endpoints and models.

- [ ] **Step 1: Add user isolation tests and 30-day midnight boundary test**
  - Create User A and User B with distinct decks, cards, and reviews.
  - Assert User A cannot see User B's reviews in `reviews_last_7_days`, streak, topics accuracy, or forecast.
  - Assert review at 30 days ago 09:00 IST is included in the 30-day topics window.
  - Assert unauthenticated requests receive 401.

- [ ] **Step 2: Run all stats tests**
  Run: `venv\Scripts\pytest backend/tests/test_stats.py -v`
  Expected: PASS.

- [ ] **Step 3: Commit**
  ```bash
  git add backend/tests/test_stats.py
  git commit -m "test(stats): add user isolation and boundary edge case tests"
  ```

---

### Task 4: Seed Script Enhancement

**Files:**
- Modify: `backend/scripts/seed.py`

**Interfaces:**
- Updates `seed_database()` to seed ~80 historical reviews over the past 14 days.
- Designates `Operating Systems` as a weak topic with >= 5 reviews and accuracy < 60%.
- Sets `CardState.last_reviewed_at` and `CardState.interval_days` on reviewed cards.
- Guarantees at least 9 consecutive review days ending today.

- [ ] **Step 1: Enhance `backend/scripts/seed.py`**
  - Add historical review generation across the existing 4 topics: `Computer Networks`, `Operating Systems`, `Database Management`, `System Design`.
  - Give `Operating Systems` 8 reviews with low ratings (e.g. 1, 2) so accuracy is < 60% and reviews_count >= 5.
  - Seed reviews over the last 14 days with at least 9 consecutive days ending today (today, today-1, ..., today-8), updating `CardState.last_reviewed_at` and `CardState.interval_days`.
  - Verify `ENV=production` guard is maintained.

- [ ] **Step 2: Execute seed script in development mode**
  Run: `python backend/scripts/seed.py`
  Expected: Completes with 0 errors and logs review counts per topic.

- [ ] **Step 3: Run full pytest suite to ensure no regressions**
  Run: `venv\Scripts\pytest -v`
  Expected: All tests pass.

- [ ] **Step 4: Commit**
  ```bash
  git add backend/scripts/seed.py
  git commit -m "chore(seed): add historical reviews and weak topic distribution to seed script"
  ```

---

### Task 5: Documentation & Phase 5 Final Verification

**Files:**
- Modify: `docs/DECISIONS.md`

- [ ] **Step 1: Document ADR-013 in `docs/DECISIONS.md`**
  - Document ADR-013: Stats & Analytics Aggregation Strategy.
  - Detail 365-day single query lookback for streak and 7-day histogram.
  - Detail IST midnight window bucketing conventions and SQLite naive datetime handling.
  - Detail Ebbinghaus retention approximation and topic accuracy join isolation.

- [ ] **Step 2: Run complete test suite**
  Run: `venv\Scripts\pytest -v`
  Expected: 100% PASS.

- [ ] **Step 3: Commit**
  ```bash
  git add docs/DECISIONS.md
  git commit -m "docs(decisions): document ADR-013 stats aggregation and streak lookback"
  ```
