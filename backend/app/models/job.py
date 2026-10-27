from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_id: Mapped[Optional[int]] = mapped_column(ForeignKey("decks.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    done_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cards_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="jobs")
    deck: Mapped[Optional["Deck"]] = relationship("Deck", back_populates="jobs")
