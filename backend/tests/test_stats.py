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

    future_review = exam_date + timedelta(days=2)
    assert calculate_expected_retention([(future_review, 5)], exam_date, today) == 100.0


# =========================================================================
# Integration Tests: Endpoints /api/stats/overview, /topics, /forecast
# =========================================================================

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_state import CardState
from app.models.review import Review
from app.core.time import today_ist, now_ist
from app.core.config import settings


def _create_user_token(client: TestClient, email: str, exam_date: str = None) -> tuple[int, str]:
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": "Stats Tester"},
    )
    user_id = reg.json()["id"]
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    token = login.json()["access_token"]
    if exam_date:
        client.patch(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"exam_date": exam_date},
        )
    return user_id, token


def test_api_stats_overview(client: TestClient, db_session: Session):
    """Test GET /api/stats/overview:
    - returns due_today, queue_size_today, daily_limit, total_cards
    - returns reviews_last_7_days with exactly 7 items
    - returns streak_days (verified with 10-day streak to prove >7)
    - returns expected_retention_on_exam, exam_date, days_to_exam
    """
    today = today_ist()
    exam_str = (today + timedelta(days=20)).isoformat()
    user_id, token = _create_user_token(client, "overview_test@example.com", exam_date=exam_str)

    # Create deck with 5 cards
    deck = Deck(user_id=user_id, title="Algorithms", source_filename="algo.txt", file_hash="hash_ov")
    db_session.add(deck)
    db_session.flush()

    cards = []
    for i in range(5):
        card = Card(
            deck_id=deck.id,
            topic="Algorithms",
            question=f"Q{i}",
            answer=f"A{i}",
            distractors=["D1", "D2", "D3"],
        )
        db_session.add(card)
        db_session.flush()
        cards.append(card)

        # 3 cards due today, 2 cards due tomorrow
        due = today if i < 3 else today + timedelta(days=1)
        state = CardState(
            card_id=card.id,
            user_id=user_id,
            ease_factor=2.5,
            interval_days=4,
            repetitions=2,
            due_date=due,
            last_reviewed_at=datetime.combine(today - timedelta(days=i), datetime.min.time(), tzinfo=IST_TIMEZONE),
            lapses=0,
        )
        db_session.add(state)

    # Insert reviews for 10 consecutive days ending today (Day 0 to Day 9)
    for day_offset in range(10):
        rev_date = today - timedelta(days=day_offset)
        rev_dt = datetime.combine(rev_date, datetime.min.time(), tzinfo=IST_TIMEZONE)
        review = Review(
            user_id=user_id,
            card_id=cards[0].id,
            rating=3,
            reviewed_at=rev_dt,
            prev_interval=1,
            new_interval=4,
        )
        db_session.add(review)

    db_session.commit()

    res = client.get("/api/stats/overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert data["due_today"] == 3
    assert data["queue_size_today"] == min(3, settings.DAILY_CARD_LIMIT)
    assert data["daily_limit"] == settings.DAILY_CARD_LIMIT
    assert data["total_cards"] == 5

    # Streak must be 10 (proves not capped at 7!)
    assert data["streak_days"] == 10

    # 7-day histogram has 7 entries, oldest first
    assert len(data["reviews_last_7_days"]) == 7
    expected_7_dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    actual_7_dates = [item["date"] for item in data["reviews_last_7_days"]]
    assert actual_7_dates == expected_7_dates
    # Each day in the last 7 days had at least 1 review
    for item in data["reviews_last_7_days"]:
        assert item["count"] >= 1

    # Exam fields
    assert data["exam_date"] == exam_str
    assert data["days_to_exam"] == 20
    assert data["expected_retention_on_exam"] is not None
    assert 0.0 <= data["expected_retention_on_exam"] <= 100.0


def test_api_stats_topics_and_sorting(client: TestClient, db_session: Session):
    """Test GET /api/stats/topics:
    - accuracy rounded to 1 decimal
    - is_weak = True only when accuracy < 60.0 AND reviews_count >= 5
    - 4 reviews with 0% accuracy -> is_weak is False
    - 5 reviews with 0% accuracy -> is_weak is True
    - Weak topics appear first, sorted by accuracy ascending, null accuracy last
    """
    today = today_ist()
    user_id, token = _create_user_token(client, "topics_test@example.com")

    deck = Deck(user_id=user_id, title="CS Topics", source_filename="cs.txt", file_hash="hash_topics")
    db_session.add(deck)
    db_session.flush()

    # Topic A: 4 reviews, all rating 1 (0% accuracy, count=4 -> NOT weak because count < 5)
    card_a = Card(deck_id=deck.id, topic="Topic A", question="QA", answer="AA", distractors=["D1", "D2", "D3"])
    db_session.add(card_a)
    db_session.flush()

    for _ in range(4):
        db_session.add(Review(
            user_id=user_id, card_id=card_a.id, rating=1, reviewed_at=now_ist(), prev_interval=1, new_interval=1
        ))

    # Topic B: 5 reviews, all rating 1 (0% accuracy, count=5 -> IS weak)
    card_b = Card(deck_id=deck.id, topic="Topic B", question="QB", answer="AB", distractors=["D1", "D2", "D3"])
    db_session.add(card_b)
    db_session.flush()

    for _ in range(5):
        db_session.add(Review(
            user_id=user_id, card_id=card_b.id, rating=1, reviewed_at=now_ist(), prev_interval=1, new_interval=1
        ))

    # Topic C: Strong topic with 6 reviews, all rating 4 (100% accuracy, count=6 -> NOT weak)
    card_c = Card(deck_id=deck.id, topic="Topic C", question="QC", answer="AC", distractors=["D1", "D2", "D3"])
    db_session.add(card_c)
    db_session.flush()

    for _ in range(6):
        db_session.add(Review(
            user_id=user_id, card_id=card_c.id, rating=4, reviewed_at=now_ist(), prev_interval=1, new_interval=2
        ))

    # Topic D: 0 reviews (accuracy=None, count=0, is_weak=False)
    card_d = Card(deck_id=deck.id, topic="Topic D", question="QD", answer="AD", distractors=["D1", "D2", "D3"])
    db_session.add(card_d)
    db_session.flush()

    db_session.commit()

    res = client.get("/api/stats/topics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    topics_list = res.json()

    # Total 4 topics
    assert len(topics_list) == 4

    # Ordering:
    # 1. Topic B (is_weak=True, acc=0.0%)
    assert topics_list[0]["topic"] == "Topic B"
    assert topics_list[0]["is_weak"] is True
    assert topics_list[0]["accuracy"] == 0.0
    assert topics_list[0]["reviews_count"] == 5

    # 2. Topic A (is_weak=False, acc=0.0%, count=4)
    assert topics_list[1]["topic"] == "Topic A"
    assert topics_list[1]["is_weak"] is False
    assert topics_list[1]["accuracy"] == 0.0
    assert topics_list[1]["reviews_count"] == 4

    # 3. Topic C (is_weak=False, acc=100.0%, count=6)
    assert topics_list[2]["topic"] == "Topic C"
    assert topics_list[2]["is_weak"] is False
    assert topics_list[2]["accuracy"] == 100.0
    assert topics_list[2]["reviews_count"] == 6

    # 4. Topic D (is_weak=False, acc=None, count=0)
    assert topics_list[3]["topic"] == "Topic D"
    assert topics_list[3]["is_weak"] is False
    assert topics_list[3]["accuracy"] is None
    assert topics_list[3]["reviews_count"] == 0


def test_api_stats_forecast(client: TestClient, db_session: Session):
    """Test GET /api/stats/forecast:
    - returns exactly 30 entries starting from today
    - overdue cards (due_date < today) folded into day 0
    - strictly ordered by date
    """
    today = today_ist()
    user_id, token = _create_user_token(client, "forecast_test@example.com")

    deck = Deck(user_id=user_id, title="Deck F", source_filename="f.txt", file_hash="hash_fc")
    db_session.add(deck)
    db_session.flush()

    # 2 cards overdue (due 2 days ago)
    # 3 cards due today
    # 1 card due tomorrow (day 1)
    # 2 cards due in 5 days (day 5)
    # 1 card due in 40 days (beyond 30 days window)
    schedule = [
        (today - timedelta(days=2), 2),
        (today, 3),
        (today + timedelta(days=1), 1),
        (today + timedelta(days=5), 2),
        (today + timedelta(days=40), 1),
    ]

    card_idx = 0
    for due, count in schedule:
        for _ in range(count):
            card = Card(
                deck_id=deck.id,
                topic="Forecast Topic",
                question=f"QFC{card_idx}",
                answer="AFC",
                distractors=["D1", "D2", "D3"],
            )
            db_session.add(card)
            db_session.flush()

            state = CardState(
                card_id=card.id,
                user_id=user_id,
                ease_factor=2.5,
                interval_days=1,
                repetitions=1,
                due_date=due,
                lapses=0,
            )
            db_session.add(state)
            card_idx += 1

    db_session.commit()

    res = client.get("/api/stats/forecast", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    forecast = data["forecast"]

    assert len(forecast) == 30

    # Day 0: today. Must include 2 overdue + 3 today = 5
    assert forecast[0]["date"] == today.isoformat()
    assert forecast[0]["due_count"] == 5

    # Day 1: tomorrow. 1 card
    assert forecast[1]["date"] == (today + timedelta(days=1)).isoformat()
    assert forecast[1]["due_count"] == 1

    # Day 5: 2 cards
    assert forecast[5]["date"] == (today + timedelta(days=5)).isoformat()
    assert forecast[5]["due_count"] == 2

    # Other days 0
    for idx in [2, 3, 4, 6, 7, 29]:
        assert forecast[idx]["due_count"] == 0


def test_api_stats_user_isolation(client: TestClient, db_session: Session):
    """Test user isolation across all stats endpoints:
    User A and User B must never see each other's metrics, review counts,
    or topic ratings, even for cards sharing the same topic name.
    """
    today = today_ist()
    user_a_id, token_a = _create_user_token(client, "isolation_a@example.com")
    user_b_id, token_b = _create_user_token(client, "isolation_b@example.com")

    # User A creates deck and card in topic "Networks"
    deck_a = Deck(user_id=user_a_id, title="Deck A", source_filename="a.txt", file_hash="hash_iso_a")
    db_session.add(deck_a)
    db_session.flush()

    card_a = Card(deck_id=deck_a.id, topic="Networks", question="Q_A", answer="A_A", distractors=["D1", "D2", "D3"])
    db_session.add(card_a)
    db_session.flush()

    state_a = CardState(
        card_id=card_a.id, user_id=user_a_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0
    )
    db_session.add(state_a)

    # User A reviews with rating 4 (100% good)
    db_session.add(Review(
        user_id=user_a_id, card_id=card_a.id, rating=4, reviewed_at=now_ist(), prev_interval=1, new_interval=2
    ))

    # User B creates deck and card in same topic "Networks"
    deck_b = Deck(user_id=user_b_id, title="Deck B", source_filename="b.txt", file_hash="hash_iso_b")
    db_session.add(deck_b)
    db_session.flush()

    card_b = Card(deck_id=deck_b.id, topic="Networks", question="Q_B", answer="A_B", distractors=["D1", "D2", "D3"])
    db_session.add(card_b)
    db_session.flush()

    # User B has 3 cards due tomorrow
    state_b = CardState(
        card_id=card_b.id, user_id=user_b_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today + timedelta(days=1), lapses=0
    )
    db_session.add(state_b)

    # User B reviews with rating 1 (0% good) across 5 reviews
    for _ in range(5):
        db_session.add(Review(
            user_id=user_b_id, card_id=card_b.id, rating=1, reviewed_at=now_ist(), prev_interval=1, new_interval=1
        ))

    db_session.commit()

    # Check User A:
    res_a_ov = client.get("/api/stats/overview", headers={"Authorization": f"Bearer {token_a}"})
    data_a_ov = res_a_ov.json()
    assert data_a_ov["total_cards"] == 1
    assert data_a_ov["due_today"] == 1
    assert data_a_ov["streak_days"] == 1

    res_a_top = client.get("/api/stats/topics", headers={"Authorization": f"Bearer {token_a}"})
    data_a_top = res_a_top.json()
    assert len(data_a_top) == 1
    assert data_a_top[0]["topic"] == "Networks"
    assert data_a_top[0]["reviews_count"] == 1
    assert data_a_top[0]["accuracy"] == 100.0
    assert data_a_top[0]["is_weak"] is False

    res_a_fc = client.get("/api/stats/forecast", headers={"Authorization": f"Bearer {token_a}"})
    data_a_fc = res_a_fc.json()["forecast"]
    assert data_a_fc[0]["due_count"] == 1  # User A has 1 card today
    assert data_a_fc[1]["due_count"] == 0  # User A has 0 cards tomorrow

    # Check User B:
    res_b_ov = client.get("/api/stats/overview", headers={"Authorization": f"Bearer {token_b}"})
    data_b_ov = res_b_ov.json()
    assert data_b_ov["total_cards"] == 1
    assert data_b_ov["due_today"] == 0  # User B's card is due tomorrow
    assert data_b_ov["streak_days"] == 1

    res_b_top = client.get("/api/stats/topics", headers={"Authorization": f"Bearer {token_b}"})
    data_b_top = res_b_top.json()
    assert len(data_b_top) == 1
    assert data_b_top[0]["topic"] == "Networks"
    assert data_b_top[0]["reviews_count"] == 5
    assert data_b_top[0]["accuracy"] == 0.0
    assert data_b_top[0]["is_weak"] is True  # 5 reviews and 0% accuracy

    res_b_fc = client.get("/api/stats/forecast", headers={"Authorization": f"Bearer {token_b}"})
    data_b_fc = res_b_fc.json()["forecast"]
    assert data_b_fc[0]["due_count"] == 0  # User B has 0 cards today
    assert data_b_fc[1]["due_count"] == 1  # User B has 1 card tomorrow


def test_api_stats_30_day_midnight_boundary(client: TestClient, db_session: Session):
    """Verify that a review within the last 30 IST days at 09:00 IST is included
    in the 30-day topics window because the window starts at IST midnight of the 30th day.
    """
    today = today_ist()
    user_id, token = _create_user_token(client, "boundary_test@example.com")

    deck = Deck(user_id=user_id, title="Boundary Deck", source_filename="b.txt", file_hash="hash_bnd")
    db_session.add(deck)
    db_session.flush()

    card = Card(deck_id=deck.id, topic="Boundary Topic", question="QB", answer="AB", distractors=["D1", "D2", "D3"])
    db_session.add(card)
    db_session.flush()

    # Review placed at exactly today - 30 days at 09:00 IST
    start_date = today - timedelta(days=30)
    review_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=IST_TIMEZONE) + timedelta(hours=9)

    db_session.add(Review(
        user_id=user_id,
        card_id=card.id,
        rating=4,
        reviewed_at=review_dt,
        prev_interval=1,
        new_interval=2,
    ))
    db_session.commit()

    res = client.get("/api/stats/topics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    topics = res.json()
    assert len(topics) == 1
    assert topics[0]["topic"] == "Boundary Topic"
    assert topics[0]["reviews_count"] == 1
    assert topics[0]["accuracy"] == 100.0


def test_api_stats_unauthenticated(client: TestClient):
    """Stats endpoints must require authentication and reject unauthenticated requests with 401."""
    res_ov = client.get("/api/stats/overview")
    assert res_ov.status_code == 401

    res_top = client.get("/api/stats/topics")
    assert res_top.status_code == 401

    res_fc = client.get("/api/stats/forecast")
    assert res_fc.status_code == 401


