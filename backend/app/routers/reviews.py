from datetime import timedelta
from typing import List, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.core.time import today_ist, now_ist
from app.core.errors import AppException
from app.models.user import User
from app.models.card import Card
from app.models.card_state import CardState
from app.models.review import Review
from app.models.deck import Deck
from app.routers.deps import get_current_user
from app.services.sm2 import calculate_sm2
from app.services.scheduler import (
    apply_exam_mode_cap,
    calculate_card_priority,
    calculate_topic_accuracy,
)
from app.schemas.review import (
    QueueResponse,
    QueueCardItem,
    PredictedIntervals,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get(
    "/queue",
    response_model=QueueResponse,
    status_code=status.HTTP_200_OK,
    summary="Get today's due cards with exam-aware priority ordering",
)
def get_review_queue(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QueueResponse:
    """Returns today's due cards for the logged-in user, capped by DAILY_CARD_LIMIT.

    Includes remaining count beyond the limit and predicted intervals for all 4 ratings.
    """
    today = today_ist()

    # Query all due cards for current user
    stmt = (
        select(CardState, Card)
        .join(Card, CardState.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(
            CardState.user_id == current_user.id,
            CardState.due_date <= today,
        )
    )
    results = db.execute(stmt).all()
    total_due = len(results)

    if total_due == 0:
        return QueueResponse(cards=[], total_due=0, remaining_count=0)

    # If user has an exam date, calculate topic accuracy over last 30 days and priority
    exam_mode_active = current_user.exam_date is not None
    topic_accuracies: Dict[str, float] = {}

    if exam_mode_active:
        thirty_days_ago = now_ist() - timedelta(days=30)
        review_stmt = (
            select(Card.topic, Review.rating)
            .join(Card, Review.card_id == Card.id)
            .where(
                Review.user_id == current_user.id,
                Review.reviewed_at >= thirty_days_ago,
            )
        )
        recent_reviews = db.execute(review_stmt).all()

        topic_ratings: Dict[str, List[int]] = {}
        for topic, rating in recent_reviews:
            topic_ratings.setdefault(topic, []).append(rating)

        for topic, ratings in topic_ratings.items():
            topic_accuracies[topic] = calculate_topic_accuracy(ratings)

    # Build queue items with calculated priorities
    scored_items = []
    for state, card in results:
        topic_acc = topic_accuracies.get(card.topic, 0.5)
        if exam_mode_active:
            p_score = calculate_card_priority(state.due_date, topic_acc, today)
        else:
            p_score = None
        scored_items.append((p_score, state, card))

    # Sort queue: exam mode -> descending priority, tie-break by due_date. Otherwise -> due_date ascending
    if exam_mode_active:
        scored_items.sort(key=lambda item: (-item[0], item[1].due_date))
    else:
        scored_items.sort(key=lambda item: item[1].due_date)

    # Apply daily card limit
    limit = settings.DAILY_CARD_LIMIT
    selected_items = scored_items[:limit]
    remaining_count = max(0, total_due - len(selected_items))

    # Format queue cards with predicted intervals for each rating
    cards_out: List[QueueCardItem] = []
    for p_score, state, card in selected_items:
        intervals = {}
        for r_code, r_name in [(1, "again"), (2, "hard"), (3, "good"), (4, "easy")]:
            res = calculate_sm2(
                ease_factor=state.ease_factor,
                interval_days=state.interval_days,
                repetitions=state.repetitions,
                rating=r_code,
                lapses=state.lapses,
                review_date=today,
            )
            capped_due = apply_exam_mode_cap(res.due_date, current_user.exam_date, today)
            intervals[r_name] = max(1, (capped_due - today).days)

        cards_out.append(
            QueueCardItem(
                card_id=card.id,
                deck_id=card.deck_id,
                topic=card.topic,
                question=card.question,
                answer=card.answer,
                distractors=card.distractors,
                ease_factor=state.ease_factor,
                interval_days=state.interval_days,
                repetitions=state.repetitions,
                due_date=state.due_date,
                lapses=state.lapses,
                predicted_intervals=PredictedIntervals(**intervals),
                priority_score=p_score,
            )
        )

    return QueueResponse(
        cards=cards_out,
        total_due=total_due,
        remaining_count=remaining_count,
    )


@router.post(
    "",
    response_model=ReviewSubmitResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a card review with SM-2 scheduling and idempotency",
)
def submit_review(
    payload: ReviewSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewSubmitResponse:
    """Records a review rating, updates card state via SM-2 in an atomic transaction,

    protects against double submission via request_id, and verifies card ownership.
    """
    today = today_ist()
    now = now_ist()

    # Verify card exists and belongs to user (using pessimistic locking on Postgres)
    state_query = (
        select(CardState)
        .join(Card, CardState.card_id == Card.id)
        .join(Deck, Card.deck_id == Deck.id)
        .where(
            CardState.card_id == payload.card_id,
            CardState.user_id == current_user.id,
        )
    )

    # Use row locking if database is PostgreSQL
    if db.bind and db.bind.dialect.name == "postgresql":
        state_query = state_query.with_for_update()

    card_state = db.scalar(state_query)
    if not card_state:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CARD_NOT_FOUND",
            message="Card not found or does not belong to you",
        )

    # Idempotency check: if request_id is provided, check if already submitted today
    if payload.request_id:
        existing_review = db.scalar(
            select(Review).where(
                Review.user_id == current_user.id,
                Review.card_id == payload.card_id,
                Review.request_id == payload.request_id,
            )
        )
        if existing_review:
            # Already processed: return current state without re-applying SM-2
            return ReviewSubmitResponse(
                card_id=card_state.card_id,
                ease_factor=card_state.ease_factor,
                interval_days=card_state.interval_days,
                repetitions=card_state.repetitions,
                due_date=card_state.due_date,
                last_reviewed_at=card_state.last_reviewed_at,
                lapses=card_state.lapses,
                prev_interval=existing_review.prev_interval,
                new_interval=existing_review.new_interval,
            )

    # Apply pure SM-2 algorithm
    prev_interval = card_state.interval_days
    sm2_res = calculate_sm2(
        ease_factor=card_state.ease_factor,
        interval_days=card_state.interval_days,
        repetitions=card_state.repetitions,
        rating=payload.rating,
        lapses=card_state.lapses,
        review_date=today,
    )

    # Apply exam mode cap if user has exam date
    capped_due_date = apply_exam_mode_cap(
        computed_due_date=sm2_res.due_date,
        exam_date=current_user.exam_date,
        review_date=today,
    )
    new_interval = max(1, (capped_due_date - today).days)

    # Update CardState atomically
    card_state.ease_factor = sm2_res.ease_factor
    card_state.interval_days = new_interval
    card_state.repetitions = sm2_res.repetitions
    card_state.due_date = capped_due_date
    card_state.last_reviewed_at = now
    card_state.lapses = sm2_res.lapses

    # Record Review history
    review_record = Review(
        user_id=current_user.id,
        card_id=card_state.card_id,
        rating=payload.rating,
        reviewed_at=now,
        prev_interval=prev_interval,
        new_interval=new_interval,
        request_id=payload.request_id,
    )
    db.add(review_record)
    db.commit()
    db.refresh(card_state)

    return ReviewSubmitResponse(
        card_id=card_state.card_id,
        ease_factor=card_state.ease_factor,
        interval_days=card_state.interval_days,
        repetitions=card_state.repetitions,
        due_date=card_state.due_date,
        last_reviewed_at=card_state.last_reviewed_at,
        lapses=card_state.lapses,
        prev_interval=prev_interval,
        new_interval=new_interval,
    )
