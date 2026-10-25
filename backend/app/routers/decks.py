from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete

from app.core.db import get_db
from app.core.errors import AppException
from app.routers.deps import get_current_user
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.job import Job
from app.schemas.deck import DeckListItem, CardResponse, DeleteDeckResponse

router = APIRouter(prefix="/decks", tags=["Decks"])


@router.get("", response_model=List[DeckListItem])
def list_decks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DeckListItem]:
    """Lists all decks belonging to the current user, along with card counts."""
    stmt = (
        select(
            Deck.id,
            Deck.title,
            Deck.source_filename,
            Deck.created_at,
            func.count(Card.id).label("card_count"),
        )
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.user_id == current_user.id)
        .group_by(Deck.id)
        .order_by(Deck.created_at.desc())
    )
    results = db.execute(stmt).all()
    return [
        DeckListItem(
            id=r.id,
            title=r.title,
            source_filename=r.source_filename,
            card_count=r.card_count,
            created_at=r.created_at,
        )
        for r in results
    ]


@router.get("/{deck_id}/cards", response_model=List[CardResponse])
def get_deck_cards(
    deck_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CardResponse]:
    """Lists cards in a deck (ownership checked)."""
    deck = db.scalar(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == current_user.id)
    )
    if not deck:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message="Deck not found",
        )

    cards = db.scalars(
        select(Card).where(Card.deck_id == deck_id).order_by(Card.id.asc())
    ).all()
    return cards


@router.delete("/{deck_id}", response_model=DeleteDeckResponse)
def delete_deck(
    deck_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteDeckResponse:
    """Deletes a deck along with its cards, states, and jobs (ownership checked)."""
    deck = db.scalar(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == current_user.id)
    )
    if not deck:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message="Deck not found",
        )

    # Delete jobs referencing this deck
    db.execute(delete(Job).where(Job.deck_id == deck.id))
    db.delete(deck)
    db.commit()

    return DeleteDeckResponse()
