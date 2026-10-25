from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class PredictedIntervals(BaseModel):
    again: int
    hard: int
    good: int
    easy: int


class QueueCardItem(BaseModel):
    card_id: int
    deck_id: int
    topic: str
    question: str
    answer: str
    distractors: List[str]
    ease_factor: float
    interval_days: int
    repetitions: int
    due_date: date
    lapses: int
    predicted_intervals: PredictedIntervals
    priority_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class QueueResponse(BaseModel):
    cards: List[QueueCardItem]
    total_due: int
    remaining_count: int


class ReviewSubmitRequest(BaseModel):
    card_id: int
    rating: int = Field(..., ge=1, le=4, description="1: Again, 2: Hard, 3: Good, 4: Easy")
    request_id: Optional[str] = Field(None, max_length=64, description="Client idempotency key")


class ReviewSubmitResponse(BaseModel):
    card_id: int
    ease_factor: float
    interval_days: int
    repetitions: int
    due_date: date
    last_reviewed_at: Optional[datetime] = None
    lapses: int
    prev_interval: int
    new_interval: int

    model_config = ConfigDict(from_attributes=True)
