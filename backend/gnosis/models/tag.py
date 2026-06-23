"""Tag SQLAlchemy model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.note import Note

# Association table for the Note <-> Tag many-to-many
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # lazy='select': explicit load only — avoids double-load collision.
    notes: Mapped[list[Note]] = relationship(
        "Note",
        secondary="note_tags",
        back_populates="tags",
        lazy="select",
    )
