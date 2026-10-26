import math
from datetime import date, timedelta
from typing import List, Optional, Set, Tuple


def calculate_expected_retention(
    cards_data: List[Tuple[Optional[date], int]],
    exam_date: Optional[date],
    current_date: date,
) -> Optional[float]:
    """Calculates expected retention percentage (0.0 to 100.0) on exam_date.

    This is an 'if you stopped revising now' estimate based on the Ebbinghaus
    forgetting curve approximation:
        R_i = exp(-t_i / S_i)
    where:
        t_i = max(0, (exam_date - last_reviewed_date).days)
        S_i = max(interval_days, 1)  (stability proxy)

    The result is the average recall probability across all reviewed cards,
    expressed as a percentage rounded to 1 decimal place.

    Returns None if:
    - exam_date is None or exam_date <= current_date
    - cards_data is empty or contains no cards with a valid last_reviewed_date
    """
    if not exam_date or exam_date <= current_date:
        return None

    recalls: List[float] = []
    for last_reviewed_date, interval_days in cards_data:
        if last_reviewed_date is None:
            continue
        t = max(0, (exam_date - last_reviewed_date).days)
        s = max(interval_days, 1)
        r_i = math.exp(-t / s)
        recalls.append(r_i)

    if not recalls:
        return None

    avg_recall = (sum(recalls) / len(recalls)) * 100.0
    return round(avg_recall, 1)


def calculate_streak(review_dates: Set[date], today: date) -> int:
    """Calculates the consecutive active review streak in days.

    Consecutive days with at least 1 review, counted backwards from today
    (or from yesterday if today has 0 reviews yet). If yesterday had 0 reviews
    and today has 0 reviews, the streak is 0.
    """
    if not review_dates:
        return 0

    if today in review_dates:
        curr = today
    elif (today - timedelta(days=1)) in review_dates:
        curr = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while curr in review_dates:
        streak += 1
        curr -= timedelta(days=1)

    return streak
