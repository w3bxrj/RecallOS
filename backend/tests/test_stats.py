import math
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest

from app.core.time import IST_TIMEZONE, to_ist_date, ist_midnight
from app.services.stats import calculate_expected_retention, calculate_streak


def test_to_ist_date_various_formats():
    """Verify to_ist_date correctly handles tz-aware UTC, tz-aware IST, naive datetimes from SQLite, and date objects."""
    # None check
    assert to_ist_date(None) is None

    # date object passthrough
    d = date(2026, 10, 26)
    assert to_ist_date(d) == d

    # tz-aware UTC (18:20 UTC = 23:50 IST same day)
    utc_dt = datetime(2026, 10, 26, 18, 20, 0, tzinfo=timezone.utc)
    assert to_ist_date(utc_dt) == date(2026, 10, 26)

    # tz-aware UTC (18:40 UTC = 00:10 IST next day)
    utc_next_dt = datetime(2026, 10, 26, 18, 40, 0, tzinfo=timezone.utc)
    assert to_ist_date(utc_next_dt) == date(2026, 10, 27)

    # tz-aware IST
    ist_dt = datetime(2026, 10, 26, 23, 50, 0, tzinfo=IST_TIMEZONE)
    assert to_ist_date(ist_dt) == date(2026, 10, 26)

    # Naive datetime from SQLite: reviews.py stores now_ist() wall clock time
    # SQLite returns naive datetime representing IST wall clock
    naive_ist_dt = datetime(2026, 10, 26, 23, 50, 0)
    assert to_ist_date(naive_ist_dt) == date(2026, 10, 26)


def test_ist_boundaries_and_midnight_windows():
    """Verify boundary conditions:
    1. Reviews at 23:50 IST and 00:10 IST land on different days.
    2. A review within the last 30 IST days but just outside 30x24 hours is included
       in the window starting at IST midnight.
    """
    dt_2350 = datetime(2026, 10, 26, 23, 50, 0, tzinfo=IST_TIMEZONE)
    dt_0010 = datetime(2026, 10, 27, 0, 10, 0, tzinfo=IST_TIMEZONE)

    assert to_ist_date(dt_2350) == date(2026, 10, 26)
    assert to_ist_date(dt_0010) == date(2026, 10, 27)
    assert to_ist_date(dt_2350) != to_ist_date(dt_0010)

    # 30-day window test
    today = date(2026, 10, 26)
    thirty_days_ago_date = today - timedelta(days=30)  # 2026-09-26
    window_start = ist_midnight(thirty_days_ago_date)  # 2026-09-26 00:00:00 IST

    # A review at 09:00 IST on 2026-09-26
    review_dt = datetime(2026, 9, 26, 9, 0, 0, tzinfo=IST_TIMEZONE)

    # Current evaluation time at 15:00 IST on 2026-10-26
    current_eval_dt = datetime(2026, 10, 26, 15, 0, 0, tzinfo=IST_TIMEZONE)

    # Elapsed time is 30 days and 6 hours (> 30 * 24 hours)
    assert (current_eval_dt - review_dt).total_seconds() > 30 * 86400

    # But review occurred on day 30 at 09:00, which is >= window_start (00:00 IST)
    assert review_dt >= window_start


def test_calculate_streak():
    """Verify streak computation logic:
    - 0 reviews -> 0
    - today only -> 1
    - yesterday only -> 1
    - 2 days ago only -> 0
    - 10-day continuous streak ending today -> 10 (proves not capped at 7)
    - 10-day continuous streak ending yesterday -> 10
    - broken streak (gap 2 days ago) -> 1
    """
    today = date(2026, 10, 26)

    # 0 reviews
    assert calculate_streak(set(), today) == 0

    # Today only
    assert calculate_streak({today}, today) == 1

    # Yesterday only
    assert calculate_streak({today - timedelta(days=1)}, today) == 1

    # 2 days ago only (streak lost)
    assert calculate_streak({today - timedelta(days=2)}, today) == 0

    # 10-day streak ending today (Day 0 to Day 9)
    ten_days_today = {today - timedelta(days=i) for i in range(10)}
    assert calculate_streak(ten_days_today, today) == 10

    # 10-day streak ending yesterday (Day 1 to Day 10)
    ten_days_yesterday = {today - timedelta(days=i) for i in range(1, 11)}
    assert calculate_streak(ten_days_yesterday, today) == 10

    # Broken streak: reviewed today, missed yesterday, reviewed 2 days ago
    broken_streak = {today, today - timedelta(days=2)}
    assert calculate_streak(broken_streak, today) == 1

    # Broken streak: missed today, reviewed yesterday, missed 2 days ago, reviewed 3 days ago
    broken_streak_yest = {today - timedelta(days=1), today - timedelta(days=3)}
    assert calculate_streak(broken_streak_yest, today) == 1


def test_calculate_expected_retention():
    """Verify Ebbinghaus forgetting curve approximation:
    R = exp(-t / S)
    where t = (exam_date - last_reviewed_date).days, S = max(interval_days, 1).
    Average across reviewed cards, rounded to 1 decimal place.
    """
    today = date(2026, 10, 26)
    exam_date = date(2026, 11, 5)  # 10 days from today

    # None / past exam date
    assert calculate_expected_retention([], None, today) is None
    assert calculate_expected_retention([], today - timedelta(days=1), today) is None
    assert calculate_expected_retention([], today, today) is None

    # No cards or only cards with None last_reviewed_date
    assert calculate_expected_retention([], exam_date, today) is None
    assert calculate_expected_retention([(None, 5)], exam_date, today) is None

    # Hand-calculated 2 cards
    # Card 1: reviewed today (t = 10), interval = 10 -> R_1 = exp(-10/10) = exp(-1) = 0.3678794
    # Card 2: reviewed 6 days ago (2026-10-20) (t = 16), interval = 16 -> R_2 = exp(-16/16) = exp(-1) = 0.3678794
    # Average = 0.3678794 * 100 = 36.8%
    cards_data = [
        (today, 10),
        (today - timedelta(days=6), 16),
    ]
    retention = calculate_expected_retention(cards_data, exam_date, today)
    assert retention == 36.8

    # Edge cases:
    # 1. interval_days = 0 -> S clamped to 1
    # Card reviewed today (t=10), interval=0 -> S=1, R = exp(-10/1) = exp(-10) = 0.0000454 -> 0.0%
    assert calculate_expected_retention([(today, 0)], exam_date, today) == 0.0

    # 2. Card with last_reviewed_date after exam_date (clamped t >= 0)
    # t = max(0, (exam_date - review_date).days) = 0 -> R = exp(0) = 1.0 -> 100.0%
    future_review = exam_date + timedelta(days=2)
    assert calculate_expected_retention([(future_review, 5)], exam_date, today) == 100.0
