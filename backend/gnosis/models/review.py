"""SM-2 spaced-repetition review card model.

Each ReviewCard is a 1-to-1 companion record for a Note.
The SM-2 algorithm fields live here so the Note model stays clean.

SM-2 reference
--------------
Original algorithm by Piotr Wozniak (SuperMemo 2).

State fields:
  easiness   -- E-factor, starts at 2.5, floor 1.3.
  interval   -- days until next review (1, 6, then calculated).
  repetitions -- consecutive correct reviews (quality >= 3).
  due_date   -- calendar date the card is next due.
  last_quality -- last rating given (0-5).
"""

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base


class ReviewCard(Base):
    """SM-2 review state for a single note."""

    __tablename__ = "review_cards"

    note_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    easiness: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_quality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    note: Mapped["Note"] = relationship(  # type: ignore[name-defined]
        "Note",
        back_populates="review_card",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewCard note_id={self.note_id!r} due={self.due_date} "
            f"interval={self.interval} easiness={self.easiness:.2f}>"
        )
