"""Tag ORM model and Note↔Tag association table."""

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.note import Note


# Association table for the many-to-many Note ↔ Tag relationship
NoteTag = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", String(20), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(100), ForeignKey("tags.name", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """A tag that can be applied to multiple notes.

    Tags are identified by their name (e.g., 'zettelkasten', 'eeg').
    """

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), default="")

    # Relationships
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        secondary="note_tags",
        back_populates="tags",
    )

    def __repr__(self) -> str:
        return f"<Tag name={self.name!r}>"
