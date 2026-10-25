from dataclasses import dataclass
from datetime import date, timedelta

# Quality mapping per PRD Section 7.1: Again = 1, Hard = 3, Good = 4, Easy = 5
RATING_TO_QUALITY = {
    1: 1,  # Again
    2: 3,  # Hard
    3: 4,  # Good
    4: 5,  # Easy
}

MIN_EASE_FACTOR = 1.3


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
    rating: int,
    lapses: int,
    review_date: date,
) -> SM2Result:
    """Pure function implementing the SuperMemo SM-2 spaced repetition algorithm.

    No database, no datetime.now() inside. Takes the reference review_date
    so all calculations are fully deterministic and unit testable.
    """
    if rating not in RATING_TO_QUALITY:
        raise ValueError(f"Rating must be between 1 and 4. Got {rating}.")

    q = RATING_TO_QUALITY[rating]

    # Interval and repetition updates
    if q < 3:
        new_repetitions = 0
        new_interval = 1
        new_lapses = lapses + 1
    else:
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * ease_factor)
        new_repetitions = repetitions + 1
        new_lapses = lapses

    # Ease factor update
    delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = max(MIN_EASE_FACTOR, ease_factor + delta_ef)

    # Next review due date
    new_due_date = review_date + timedelta(days=new_interval)

    return SM2Result(
        ease_factor=new_ef,
        interval_days=new_interval,
        repetitions=new_repetitions,
        due_date=new_due_date,
        lapses=new_lapses,
    )
