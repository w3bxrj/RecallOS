from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DailyReviewCount(BaseModel):
    date: str
    count: int

    model_config = ConfigDict(from_attributes=True)


class StatsOverviewResponse(BaseModel):
    due_today: int
    queue_size_today: int
    daily_limit: int
    total_cards: int
    reviews_last_7_days: List[DailyReviewCount]
    streak_days: int
    expected_retention_on_exam: Optional[float] = None
    exam_date: Optional[date] = None
    days_to_exam: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class TopicAccuracyItem(BaseModel):
    topic: str
    accuracy: Optional[float] = None
    reviews_count: int
    is_weak: bool

    model_config = ConfigDict(from_attributes=True)


class ForecastItem(BaseModel):
    date: str
    due_count: int

    model_config = ConfigDict(from_attributes=True)


class ForecastResponse(BaseModel):
    forecast: List[ForecastItem]

    model_config = ConfigDict(from_attributes=True)
