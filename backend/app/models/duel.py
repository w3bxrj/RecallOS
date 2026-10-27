from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


# NOTE: The 'duels' model and table are reserved for the planned future
# real-time Quiz Duel feature (PRD section 9.2). This feature is not implemented
# in the current submission. Retained to preserve database schema integrity.
class Duel(Base):
    __tablename__ = "duels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"), nullable=False, index=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="waiting", nullable=False)
    host_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    guest_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    deck: Mapped["Deck"] = relationship("Deck", back_populates="duels")
    host: Mapped["User"] = relationship("User", foreign_keys=[host_id])
    guest: Mapped[Optional["User"]] = relationship("User", foreign_keys=[guest_id])
    winner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[winner_id])
