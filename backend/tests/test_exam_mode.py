from datetime import date, timedelta
import pytest
from app.services.scheduler import apply_exam_mode_cap, calculate_card_priority, calculate_topic_accuracy


def test_apply_exam_mode_cap_future_exam() -> None:
    """When exam is in 10 days, cap due_date to exam_date - 1 day (9 days)."""
    today = date(2026, 10, 25)
    exam = date(2026, 11, 4)  # 10 days away
    computed_due_date = today + timedelta(days=15)  # 15 days computed by SM-2

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    # Capped to 2026-11-03 (exam - 1 day)
    assert capped == date(2026, 11, 3)


def test_apply_exam_mode_cap_does_not_shorten_if_earlier_than_cap() -> None:
    """If computed due date is earlier than cap, it remains unchanged."""
    today = date(2026, 10, 25)
    exam = date(2026, 11, 4)  # 10 days away
    computed_due_date = today + timedelta(days=3)

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    assert capped == today + timedelta(days=3)


def test_apply_exam_mode_cap_never_earlier_than_tomorrow() -> None:
    """Capped date is never earlier than tomorrow."""
    today = date(2026, 10, 25)
    exam = today + timedelta(days=2)  # Exam in 2 days (exam - 1 is tomorrow)
    computed_due_date = today + timedelta(days=5)

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    assert capped == today + timedelta(days=1)


def test_apply_exam_mode_cap_exam_tomorrow() -> None:
    """Edge case: Exam tomorrow -> capped to tomorrow."""
    today = date(2026, 10, 25)
    exam = today + timedelta(days=1)
    computed_due_date = today + timedelta(days=6)

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    assert capped == today + timedelta(days=1)


def test_apply_exam_mode_cap_exam_today() -> None:
    """Edge case: Exam today -> capped to tomorrow."""
    today = date(2026, 10, 25)
    exam = today
    computed_due_date = today + timedelta(days=6)

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    assert capped == today + timedelta(days=1)


def test_apply_exam_mode_cap_exam_in_past() -> None:
    """Edge case: Exam in the past -> capped to tomorrow."""
    today = date(2026, 10, 25)
    exam = today - timedelta(days=5)
    computed_due_date = today + timedelta(days=6)

    capped = apply_exam_mode_cap(
        computed_due_date=computed_due_date,
        exam_date=exam,
        review_date=today,
    )
    assert capped == today + timedelta(days=1)


def test_apply_exam_mode_cap_no_exam_date() -> None:
    """Without exam date, due_date is returned unchanged."""
    today = date(2026, 10, 25)
    computed = today + timedelta(days=12)
    assert apply_exam_mode_cap(computed, exam_date=None, review_date=today) == computed


def test_priority_formula_calculation() -> None:
    """Priority: (1 - topic_accuracy) * 0.6 + overdue_days_normalised * 0.4."""
    today = date(2026, 10, 25)
    # Overdue by 15 days -> 15 / 30 = 0.5 normalized
    due_date = today - timedelta(days=15)
    # topic accuracy 0.4 -> (1 - 0.4) * 0.6 = 0.36
    # overdue part -> 0.5 * 0.4 = 0.20
    # priority = 0.36 + 0.20 = 0.56
    p = calculate_card_priority(card_due_date=due_date, topic_accuracy=0.4, today=today)
    assert pytest.approx(p, 0.001) == 0.56


def test_priority_formula_not_overdue() -> None:
    """Due today or upcoming has 0 overdue component."""
    today = date(2026, 10, 25)
    due_date = today
    # topic accuracy 0.8 -> (1 - 0.8) * 0.6 = 0.12
    p = calculate_card_priority(card_due_date=due_date, topic_accuracy=0.8, today=today)
    assert pytest.approx(p, 0.001) == 0.12


def test_topic_accuracy_less_than_5_reviews_is_neutral() -> None:
    """Topics with fewer than 5 reviews default to 0.5 accuracy."""
    reviews_3_good = [3, 4, 3]  # only 3 reviews
    acc = calculate_topic_accuracy(reviews_3_good)
    assert acc == 0.5


def test_topic_accuracy_5_or_more_reviews() -> None:
    """Topics with 5+ reviews compute ratio of (Good or Easy) / total."""
    # 3 Good/Easy (3, 4) and 2 Again/Hard (1, 2) out of 5 -> 3/5 = 0.6
    reviews = [1, 2, 3, 4, 4]
    acc = calculate_topic_accuracy(reviews)
    assert pytest.approx(acc, 0.001) == 0.6
