from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.time import today_ist, now_ist
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_state import CardState
from app.models.review import Review


def create_user_and_token(client: TestClient, email: str, exam_date: str = None) -> tuple[int, str]:
    """Helper to register and login a user, returning (user_id, token)."""
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": "Test User"},
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


def test_get_queue_empty_when_no_cards_due(client: TestClient) -> None:
    """When user has no cards due today, returns empty cards list and zero counts."""
    _, token = create_user_and_token(client, "emptyqueue@example.com")
    res = client.get("/api/reviews/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["cards"] == []
    assert data["total_due"] == 0
    assert data["remaining_count"] == 0


def test_get_queue_returns_due_cards_with_predicted_intervals(
    client: TestClient, db_session: Session
) -> None:
    """Due cards are returned with all 4 predicted intervals for frontend rating buttons."""
    user_id, token = create_user_and_token(client, "dueuser@example.com")
    today = today_ist()

    # Create deck and card
    deck = Deck(user_id=user_id, title="Test Deck", source_filename="test.pdf", file_hash="hash1")
    db_session.add(deck)
    db_session.flush()

    card = Card(
        deck_id=deck.id,
        topic="Networking",
        question="What is IP?",
        answer="Internet Protocol",
        distractors=["A", "B", "C"],
    )
    db_session.add(card)
    db_session.flush()

    state = CardState(
        card_id=card.id,
        user_id=user_id,
        ease_factor=2.5,
        interval_days=1,
        repetitions=1,
        due_date=today,
        lapses=0,
    )
    db_session.add(state)
    db_session.commit()

    res = client.get("/api/reviews/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_due"] == 1
    assert data["remaining_count"] == 0
    assert len(data["cards"]) == 1

    item = data["cards"][0]
    assert item["card_id"] == card.id
    assert item["topic"] == "Networking"
    assert "predicted_intervals" in item
    pred = item["predicted_intervals"]
    # Again resets to 1, Good on rep=1 gives 6
    assert pred["again"] == 1
    assert pred["good"] == 6
    assert pred["hard"] >= 1
    assert pred["easy"] >= pred["good"]


def test_get_queue_exam_mode_priority_ordering(client: TestClient, db_session: Session) -> None:
    """In exam mode, weak topics and overdue cards receive higher priority and appear first."""
    today = today_ist()
    exam_str = (today + timedelta(days=20)).isoformat()
    user_id, token = create_user_and_token(client, "examqueue@example.com", exam_date=exam_str)

    deck = Deck(user_id=user_id, title="Exam Deck", source_filename="exam.pdf", file_hash="hash2")
    db_session.add(deck)
    db_session.flush()

    # Card 1: Fresh topic (accuracy neutral 0.5), due today
    card1 = Card(deck_id=deck.id, topic="Topic Neutral", question="Q1", answer="A1", distractors=["w1", "w2", "w3"])
    db_session.add(card1)
    db_session.flush()
    state1 = CardState(card_id=card1.id, user_id=user_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0)
    db_session.add(state1)

    # Card 2: Weak topic (accuracy 0.2), overdue by 10 days
    card2 = Card(deck_id=deck.id, topic="Topic Weak", question="Q2", answer="A2", distractors=["w1", "w2", "w3"])
    db_session.add(card2)
    db_session.flush()
    state2 = CardState(card_id=card2.id, user_id=user_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today - timedelta(days=10), lapses=0)
    db_session.add(state2)

    # Add 5 reviews for Topic Weak with mostly ratings 1 and 2 (poor accuracy: 1/5 = 0.2)
    for r in [1, 1, 2, 2, 4]:
        db_session.add(Review(user_id=user_id, card_id=card2.id, rating=r, reviewed_at=now_ist(), prev_interval=1, new_interval=1))

    db_session.commit()

    res = client.get("/api/reviews/queue", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    cards = res.json()["cards"]
    assert len(cards) == 2
    # Card 2 has weak topic (0.2 accuracy) + 10 days overdue -> priority is strictly higher -> first
    assert cards[0]["card_id"] == card2.id
    assert cards[1]["card_id"] == card1.id
    assert cards[0]["priority_score"] > cards[1]["priority_score"]


def test_submit_review_success_updates_sm2_and_due_date(
    client: TestClient, db_session: Session
) -> None:
    """Submitting rating Good (3) updates card_state according to SM-2 and records a Review."""
    user_id, token = create_user_and_token(client, "reviewer@example.com")
    today = today_ist()

    deck = Deck(user_id=user_id, title="Deck", source_filename="file.pdf", file_hash="hash3")
    db_session.add(deck)
    db_session.flush()
    card = Card(deck_id=deck.id, topic="Topic", question="Q", answer="A", distractors=["w1", "w2", "w3"])
    db_session.add(card)
    db_session.flush()
    state = CardState(card_id=card.id, user_id=user_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0)
    db_session.add(state)
    db_session.commit()

    # Submit Good (rating=3)
    response = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"card_id": card.id, "rating": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["card_id"] == card.id
    assert data["repetitions"] == 2
    assert data["interval_days"] == 6
    assert data["due_date"] == (today + timedelta(days=6)).isoformat()

    # Check Review row in DB
    db_review = db_session.query(Review).filter(Review.card_id == card.id).first()
    assert db_review is not None
    assert db_review.rating == 3
    assert db_review.prev_interval == 1
    assert db_review.new_interval == 6


def test_submit_review_ownership_check(client: TestClient, db_session: Session) -> None:
    """User B cannot review User A's card; returns 404 CARD_NOT_FOUND."""
    user_a_id, _ = create_user_and_token(client, "usera@example.com")
    _, user_b_token = create_user_and_token(client, "userb@example.com")
    today = today_ist()

    deck = Deck(user_id=user_a_id, title="Deck A", source_filename="a.pdf", file_hash="hash_a")
    db_session.add(deck)
    db_session.flush()
    card = Card(deck_id=deck.id, topic="Topic", question="Q", answer="A", distractors=["w1", "w2", "w3"])
    db_session.add(card)
    db_session.flush()
    state = CardState(card_id=card.id, user_id=user_a_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0)
    db_session.add(state)
    db_session.commit()

    # User B attempts to review User A's card
    res = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_b_token}"},
        json={"card_id": card.id, "rating": 3},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "CARD_NOT_FOUND"


def test_submit_review_idempotency_duplicate_request_id(
    client: TestClient, db_session: Session
) -> None:
    """Duplicate review submission with same request_id does not apply SM-2 twice."""
    user_id, token = create_user_and_token(client, "idempotent@example.com")
    today = today_ist()

    deck = Deck(user_id=user_id, title="Deck", source_filename="f.pdf", file_hash="hash4")
    db_session.add(deck)
    db_session.flush()
    card = Card(deck_id=deck.id, topic="Topic", question="Q", answer="A", distractors=["w1", "w2", "w3"])
    db_session.add(card)
    db_session.flush()
    state = CardState(card_id=card.id, user_id=user_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0)
    db_session.add(state)
    db_session.commit()

    req_id = "unique-client-req-999"

    # First submission
    res1 = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"card_id": card.id, "rating": 3, "request_id": req_id},
    )
    assert res1.status_code == 200
    assert res1.json()["repetitions"] == 2
    assert res1.json()["interval_days"] == 6

    # Duplicate submission
    res2 = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"card_id": card.id, "rating": 3, "request_id": req_id},
    )
    assert res2.status_code == 200
    # State remains identical, NOT incremented to repetition 3 or interval 15
    assert res2.json()["repetitions"] == 2
    assert res2.json()["interval_days"] == 6

    # Verify only 1 review record was inserted in DB
    reviews_count = db_session.query(Review).filter(Review.card_id == card.id).count()
    assert reviews_count == 1


def test_submit_review_exam_mode_cap(client: TestClient, db_session: Session) -> None:
    """Review in exam mode caps new due_date to exam_date - 1 day."""
    today = today_ist()
    exam_d = today + timedelta(days=4)  # Exam in 4 days
    user_id, token = create_user_and_token(client, "examcap@example.com", exam_date=exam_d.isoformat())

    deck = Deck(user_id=user_id, title="Deck", source_filename="f.pdf", file_hash="hash5")
    db_session.add(deck)
    db_session.flush()
    card = Card(deck_id=deck.id, topic="Topic", question="Q", answer="A", distractors=["w1", "w2", "w3"])
    db_session.add(card)
    db_session.flush()
    # Repetition 1 -> Good would normally produce interval 6 days!
    state = CardState(card_id=card.id, user_id=user_id, ease_factor=2.5, interval_days=1, repetitions=1, due_date=today, lapses=0)
    db_session.add(state)
    db_session.commit()

    res = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {token}"},
        json={"card_id": card.id, "rating": 3},
    )
    assert res.status_code == 200
    data = res.json()
    # Normally interval would be 6, but exam is in 4 days -> capped to exam - 1 day (3 days)
    assert data["interval_days"] == 3
    assert data["due_date"] == (today + timedelta(days=3)).isoformat()
