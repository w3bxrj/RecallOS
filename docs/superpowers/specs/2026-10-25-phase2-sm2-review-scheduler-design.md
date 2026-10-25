# RecallOS Phase 2 Design Specification: SM-2, Review Engine & Scheduler

## 1. Overview & Scope
Phase 2 implements the scientific core of RecallOS:
- Pure-function SM-2 spaced repetition calculation module (`services/sm2.py`).
- Timezone helpers for `Asia/Kolkata` (`core/time.py`) and schema update for `due_date` as SQL `Date`.
- Exam-mode interval capping and queue prioritization (`services/scheduler.py`).
- Daily review queue endpoint (`GET /api/reviews/queue`) with interval preview for all 4 ratings and limit pagination.
- Atomic review submission endpoint (`POST /api/reviews`) with row locking, idempotency protection via `request_id`, and strict ownership verification.
- Seed script (`scripts/seed.py`) generating 30 cards across 4 topics for manual and automated testing.
- Comprehensive unit and integration test suite.

## 2. Component Design & Interfaces

### 2.1 Pure SM-2 Engine (`app/services/sm2.py`)
No database or global state dependencies. Deterministic calculation:
```python
@dataclass(frozen=True)
class SM2Result:
    ease_factor: float
    interval_days: int
    repetitions: int
    due_date: date
    lapses: int

def calculate_sm2(
    ease_factor: float,
    interval_days: int,
    repetitions: int,
    rating: int,        # 1: Again, 2: Hard, 3: Good, 4: Easy
    lapses: int,
    review_date: date,  # Reference date for deterministic calculation
) -> SM2Result
```
- Mapping of rating to quality `q`:
  - 1 (Again) -> q = 1
  - 2 (Hard)  -> q = 3
  - 3 (Good)  -> q = 4
  - 4 (Easy)  -> q = 5
- Algorithm:
  - If `q < 3`: `repetitions = 0`, `interval = 1`, `lapses += 1`
  - Else:
    - If `repetitions == 0`: `interval = 1`
    - Elif `repetitions == 1`: `interval = 6`
    - Else: `interval = round(interval * ease_factor)`
    - `repetitions += 1`
  - `ease_factor = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))`
  - `ease_factor = max(ease_factor, 1.3)`
  - `due_date = review_date + timedelta(days=interval)`

### 2.2 Timezone Utilities (`app/core/time.py`)
- Canonical timezone: `Asia/Kolkata`
- `now_ist() -> datetime` (timezone-aware)
- `today_ist() -> date`

### 2.3 Scheduler & Exam Mode (`app/services/scheduler.py`)
- **Exam Date Capping:**
  - Cap new `due_date` so it is never later than `exam_date - 1 day`.
  - Cap is never earlier than tomorrow (`review_date + 1 day`).
  - If `exam_date <= review_date + 1 day`, returns tomorrow (`review_date + 1 day`).
- **Queue Prioritization:**
  - Overdue days: `overdue_days = max(0, (today - card_state.due_date).days)`
  - Normalization: `overdue_days_normalised = min(1.0, overdue_days / 30.0)`
  - Topic Accuracy: 30-day window review share of ratings 3 or 4. If total reviews < 5, accuracy is 0.5.
  - Priority formula: `priority = (1 - topic_accuracy) * 0.6 + overdue_days_normalised * 0.4`
  - Ordering:
    - If exam mode active: descending by `priority`, tie-break by `due_date` ascending.
    - If no exam date: ascending by `due_date`.

### 2.4 API Endpoints
- `GET /api/reviews/queue`:
  - Filter: `card_states.user_id == current_user.id` and `card_states.due_date <= today_ist()`
  - Order: via `scheduler.order_queue`
  - Limit: `settings.DAILY_CARD_LIMIT`
  - Calculates predicted intervals for all 4 ratings for each card using `calculate_sm2`.
- `POST /api/reviews`:
  - Body: `card_id: int`, `rating: int (1..4)`, `request_id: Optional[str] = None`
  - Verifies card ownership (returns 404 `CARD_NOT_FOUND` if card doesn't belong to current user).
  - Idempotency: If `request_id` is supplied and matching review exists for today, return current state without re-applying SM-2.
  - Applies SM-2, updates `card_states`, records `Review`, commits atomically.
