from datetime import date, datetime, timedelta
from typing import Optional, Union, List


def apply_exam_mode_cap(
    computed_due_date: date,
    exam_date: Optional[Union[date, datetime]],
    review_date: date,
) -> date:
    """Caps the computed due date so it is never later than exam_date - 1 day,

    and never earlier than tomorrow (review_date + 1 day).
    If no exam date is set, returns computed_due_date unmodified.
    """
    if exam_date is None:
        return computed_due_date

    # Convert datetime to date if needed
    exam_d = exam_date.date() if isinstance(exam_date, datetime) else exam_date

    tomorrow = review_date + timedelta(days=1)
    exam_cap = exam_d - timedelta(days=1)

    if exam_cap < tomorrow:
        return tomorrow

    return max(tomorrow, min(computed_due_date, exam_cap))


def calculate_topic_accuracy(ratings: List[int]) -> float:
    """Calculates accuracy for a topic based on ratings in the last 30 days.

    Good (3) and Easy (4) are counted as correct.
    If a topic has fewer than 5 reviews, returns neutral 0.5.
    """
    if len(ratings) < 5:
        return 0.5

    correct_count = sum(1 for r in ratings if r in (3, 4))
    return round(correct_count / len(ratings), 4)


def calculate_card_priority(
    card_due_date: date,
    topic_accuracy: float,
    today: date,
) -> float:
    """Calculates queue priority score for exam mode:

    priority = (1 - topic_accuracy) * 0.6 + overdue_days_normalised * 0.4.
    Higher score indicates higher study urgency (weak topics and overdue cards first).
    """
    overdue_days = max(0, (today - card_due_date).days)
    overdue_days_normalised = min(1.0, overdue_days / 30.0)

    priority = (1.0 - topic_accuracy) * 0.6 + overdue_days_normalised * 0.4
    return round(priority, 4)
