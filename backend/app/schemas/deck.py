from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DeckListItem(BaseModel):
    """Deck item returned in deck list."""
    id: int
    title: str
    source_filename: str
    card_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CardResponse(BaseModel):
    """Card item returned in deck cards list."""
    id: int
    deck_id: int
    topic: str
    question: str
    answer: str
    distractors: List[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeleteDeckResponse(BaseModel):
    """Response returned upon deck deletion."""
    status: str = "ok"
    message: str = "Deck deleted successfully"
