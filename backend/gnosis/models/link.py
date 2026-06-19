"""Link ORM model — represents a directed wikilink between two notes."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.note import Note


class Link(Base):
    """A directed link from one note to another.

    Represents [[WikiLink]] references extracted from note bodies.
    Both `source_id` and `target_id` reference the Note table.
    """

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source_id: Mapped[str] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), index=True
    )

    link_text: Mapped[str] = mapped_column(
        String(500)
    )  # The [[Link Text]] as written in the source note
    context: Mapped[Optional[str]] = mapped_column(
        Text
    )  # Surrounding paragraph for context
    link_type: Mapped[str] = mapped_column(
        String(50), default="wikilink"
    )  # wikilink | mention | citation

    # Relationships
    source: Mapped["Note"] = relationship("Note", foreign_keys=[source_id], back_populates="outgoing_links")
    target: Mapped["Note"] = relationship("Note", foreign_keys=[target_id], back_populates="incoming_links")

    def __repr__(self) -> str:
        return f"<Link {self.source_id!r} → {self.target_id!r} [{self.link_text!r}]>"
