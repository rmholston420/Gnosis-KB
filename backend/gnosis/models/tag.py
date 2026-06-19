"""Tag and NoteTag association models."""

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

# Many-to-many association table: note <-> tag
NoteTag = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", String(20), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(100), ForeignKey("tags.name", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    """A note tag (folksonomy-style)."""

    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), default="")

    notes: Mapped[list] = relationship(
        "Note",
        secondary="note_tags",
        back_populates="tags",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Tag name={self.name!r}>"
