"""ReviewCard SQLAlchemy model for SM-2 spaced-repetition scheduling."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.note import Note


class ReviewCard(Base):
    """Tracks the SM-2 state for a single Note.

    Each enrolled note gets exactly one ReviewCard row.  The SM-2 scheduler
    (gnosis/core/sm2.py) reads and updates easiness, interval, repetitions,
    and due_date on every review submission.
    """

    __tablename__ = "review_cards"

    note_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    easiness: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    # lazy="select": load Note on first access within the session.
    # Using selectin here caused a conflict with the Note model's
    # eagerly-loaded attribute 'Note.tags' which collapsed Note.tags to a
    # scalar and broke the tags API response.
    note: Mapped["Note"] = relationship(  # type: ignore[name-defined]
        "Note",
        back_populates="review_card",
        lazy="select",
    )
