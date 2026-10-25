from datetime import date, timedelta
import pytest
from app.services.sm2 import calculate_sm2, SM2Result


def test_first_review_good() -> None:
    """First review with Good (3) produces interval 1 and increments repetitions to 1."""
    today = date(2026, 10, 25)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=0,
        repetitions=0,
        rating=3,  # Good (q=4)
        lapses=0,
        review_date=today,
    )
    assert res.interval_days == 1
    assert res.repetitions == 1
    assert res.lapses == 0
    assert res.due_date == today + timedelta(days=1)
    # EF adjustment for q=4: 0.1 - (1) * (0.08 + 0.02) = 0.1 - 0.1 = 0 -> EF remains 2.5
    assert pytest.approx(res.ease_factor, 0.001) == 2.5


def test_second_review_good() -> None:
    """Second review with Good (3) produces interval 6 and increments repetitions to 2."""
    today = date(2026, 10, 26)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=1,
        repetitions=1,
        rating=3,  # Good (q=4)
        lapses=0,
        review_date=today,
    )
    assert res.interval_days == 6
    assert res.repetitions == 2
    assert res.due_date == today + timedelta(days=6)


def test_third_review_good_uses_ease_factor() -> None:
    """Third review with Good uses interval = round(interval * EF)."""
    today = date(2026, 11, 1)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=6,
        repetitions=2,
        rating=3,  # Good (q=4)
        lapses=0,
        review_date=today,
    )
    # round(6 * 2.5) = 15
    assert res.interval_days == 15
    assert res.repetitions == 3
    assert res.due_date == today + timedelta(days=15)


def test_again_resets_repetitions_and_interval_and_increments_lapses() -> None:
    """Rating Again (1) resets repetitions to 0, interval to 1, and increments lapses."""
    today = date(2026, 11, 15)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=15,
        repetitions=3,
        rating=1,  # Again (q=1)
        lapses=1,
        review_date=today,
    )
    assert res.interval_days == 1
    assert res.repetitions == 0
    assert res.lapses == 2
    assert res.due_date == today + timedelta(days=1)


def test_easy_raises_ease_factor() -> None:
    """Rating Easy (4, q=5) raises ease factor."""
    today = date(2026, 10, 25)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=1,
        repetitions=1,
        rating=4,  # Easy (q=5)
        lapses=0,
        review_date=today,
    )
    # q=5: EF = 2.5 + (0.1 - 0) = 2.6
    assert pytest.approx(res.ease_factor, 0.001) == 2.6
    assert res.ease_factor > 2.5


def test_hard_lowers_ease_factor() -> None:
    """Rating Hard (2, q=3) lowers ease factor."""
    today = date(2026, 10, 25)
    res = calculate_sm2(
        ease_factor=2.5,
        interval_days=1,
        repetitions=1,
        rating=2,  # Hard (q=3)
        lapses=0,
        review_date=today,
    )
    # q=3: 5 - 3 = 2 -> 0.1 - (2 * (0.08 + 2 * 0.02)) = 0.1 - 2 * 0.12 = 0.1 - 0.24 = -0.14
    # EF = 2.5 - 0.14 = 2.36
    assert pytest.approx(res.ease_factor, 0.001) == 2.36
    assert res.ease_factor < 2.5


def test_ease_factor_floor_never_drops_below_1_point_3() -> None:
    """Ease factor never drops below 1.3 even after multiple consecutive Hard/Again ratings."""
    today = date(2026, 10, 25)
    res = calculate_sm2(
        ease_factor=1.35,
        interval_days=5,
        repetitions=2,
        rating=1,  # Again (q=1, drops EF by 0.54)
        lapses=0,
        review_date=today,
    )
    assert res.ease_factor == 1.3


def test_invalid_rating_raises_value_error() -> None:
    """Invalid rating outside 1..4 raises ValueError."""
    today = date(2026, 10, 25)
    with pytest.raises(ValueError, match="Rating must be between 1 and 4"):
        calculate_sm2(
            ease_factor=2.5,
            interval_days=1,
            repetitions=1,
            rating=5,
            lapses=0,
            review_date=today,
        )
