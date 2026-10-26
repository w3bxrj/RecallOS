from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case

from app.core.config import settings
from app.core.db import get_db
from app.core.time import today_ist, to_ist_date, ist_midnight
from app.models.user import User
from app.models.card import Card
from app.models.card_state import CardState
from app.models.review import Review
from app.models.deck import Deck
from app.routers.deps import get_current_user
from app.services.stats import calculate_expected_retention, calculate_streak
from app.schemas.stats import (
    StatsOverviewResponse,
    DailyReviewCount,
    TopicAccuracyItem,
    ForecastResponse,
    ForecastItem,
)

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get(
    "/overview",
    response_model=StatsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user learning stats overview including streak and retention estimate",
)
def get_stats_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsOverviewResponse:
    """Returns overview stats for the logged-in user.

    Uses a single 365-day review lookback to compute streak and the 7-day histogram,
    preventing any 7-day streak cap while avoiding redundant queries.
    """
    today = today_ist()

    # 1. 365-day review lookback for streak and 7-day histogram
    cutoff_365d = ist_midnight(today - timedelta(days=365))
    review_stmt = (
        select(Review.reviewed_at)
        .where(
            Review.user_id == current_user.id,
            Review.reviewed_at >= cutoff_365d,
        )
    )
    review_timestamps = db.scalars(review_stmt).all()
    review_dates_list = [to_ist_date(ts) for ts in review_timestamps if ts is not None]
    review_dates_set = set(review_dates_list)

    streak_days = calculate_streak(review_dates_set, today)

    # 7-day histogram reuses the same 365-day reviews query result
    seven_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    reviews_last_7_days = [
        DailyReviewCount(
            date=d.isoformat(),
            count=sum(1 for rd in review_dates_list if rd == d),
        )
        for d in seven_days
    ]

    # 2. Due cards count and limits
    due_stmt = (
        select(func.count(CardState.id))
        .where(
            CardState.user_id == current_user.id,
            CardState.due_date <= today,
        )
    )
    due_today = db.scalar(due_stmt) or 0
    queue_size_today = min(due_today, settings.DAILY_CARD_LIMIT)
    daily_limit = settings.DAILY_CARD_LIMIT

    # 3. Total cards count
    total_cards_stmt = (
        select(func.count(Card.id))
        .join(Deck, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id)
    )
    total_cards = db.scalar(total_cards_stmt) or 0

    # 4. Exam date and expected retention calculation
    user_exam_date = to_ist_date(current_user.exam_date)
    if user_exam_date and user_exam_date > today:
        days_to_exam = (user_exam_date - today).days
        # Load reviewed cards (skipping null last_reviewed_at)
        card_states_stmt = (
            select(CardState.last_reviewed_at, CardState.interval_days)
            .where(
                CardState.user_id == current_user.id,
                CardState.last_reviewed_at.isnot(None),
            )
        )
        rows = db.execute(card_states_stmt).all()
        cards_data = [(to_ist_date(r[0]), r[1]) for r in rows]
        expected_retention = calculate_expected_retention(cards_data, user_exam_date, today)
    else:
        days_to_exam = None
        expected_retention = None

    return StatsOverviewResponse(
        due_today=due_today,
        queue_size_today=queue_size_today,
        daily_limit=daily_limit,
        total_cards=total_cards,
        reviews_last_7_days=reviews_last_7_days,
        streak_days=streak_days,
        expected_retention_on_exam=expected_retention,
        exam_date=user_exam_date,
        days_to_exam=days_to_exam,
    )


@router.get(
    "/topics",
    response_model=List[TopicAccuracyItem],
    status_code=status.HTTP_200_OK,
    summary="Get per-topic accuracy and weak topic identification",
)
def get_stats_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TopicAccuracyItem]:
    """Returns topic accuracy over the last 30 days for cards in user-owned decks.

    Accuracy is share of reviews with rating >= 3 over last 30 IST days (rounded to 1 decimal).
    Weak topics (accuracy < 60% with >= 5 reviews) are sorted first, followed by accuracy asc.
    """
    today = today_ist()
    cutoff_30d = ist_midnight(today - timedelta(days=30))

    # Aggregate topic statistics with strict user isolation on the reviews join
    stmt = (
        select(
            Card.topic,
            func.count(Review.id).label("reviews_count"),
            func.coalesce(func.sum(case((Review.rating >= 3, 1), else_=0)), 0).label("good_count"),
        )
        .join(Deck, Card.deck_id == Deck.id)
        .outerjoin(
            Review,
            (Review.card_id == Card.id)
            & (Review.user_id == current_user.id)
            & (Review.reviewed_at >= cutoff_30d),
        )
        .where(Deck.user_id == current_user.id)
        .group_by(Card.topic)
    )
    results = db.execute(stmt).all()

    items: List[TopicAccuracyItem] = []
    for row in results:
        count = row.reviews_count
        good = row.good_count
        if count == 0:
            acc = None
            is_weak = False
        else:
            acc = round((good / count) * 100.0, 1)
            is_weak = (acc < 60.0) and (count >= 5)

        items.append(
            TopicAccuracyItem(
                topic=row.topic,
                accuracy=acc,
                reviews_count=count,
                is_weak=is_weak,
            )
        )

    # Sort: weak topics first, then by accuracy ascending (nulls last), then topic name
    def sort_key(item: TopicAccuracyItem):
        weak_rank = 0 if item.is_weak else 1
        acc_rank = item.accuracy if item.accuracy is not None else float("inf")
        return (weak_rank, acc_rank, item.topic)

    items.sort(key=sort_key)
    return items


@router.get(
    "/forecast",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 30-day review workload forecast",
)
def get_stats_forecast(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    """Returns exactly 30 entries of daily due card forecasts starting today.

    Overdue cards (due_date < today) are folded into day 0 (today's count).
    """
    today = today_ist()

    # Query due_date distribution for current user
    stmt = (
        select(CardState.due_date, func.count(CardState.id))
        .where(CardState.user_id == current_user.id)
        .group_by(CardState.due_date)
    )
    results = db.execute(stmt).all()

    # Initialize 30 days
    days_30 = [today + timedelta(days=i) for i in range(30)]
    forecast_counts = {d: 0 for d in days_30}

    for due_date, count in results:
        if due_date is None:
            continue
        if due_date <= today:
            forecast_counts[today] += count
        elif due_date in forecast_counts:
            forecast_counts[due_date] += count

    forecast_items = [
        ForecastItem(date=d.isoformat(), due_count=forecast_counts[d])
        for d in days_30
    ]
    return ForecastResponse(forecast=forecast_items)
