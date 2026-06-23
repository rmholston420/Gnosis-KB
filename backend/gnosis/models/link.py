"""Link model (directional wikilinks between notes)."""


from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base


class Link(Base):
    """A directional link from source_note to target_note.

    Extracted from [[WikiLink]] patterns in note body text.
    """

    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_text: Mapped[str] = mapped_column(String(500), nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_type: Mapped[str] = mapped_column(String(50), default="wikilink")

    # Relationships
    source_note: Mapped["Note"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Note",
        foreign_keys=[source_id],
        back_populates="outgoing_links",
    )
    target_note: Mapped["Note"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Note",
        foreign_keys=[target_id],
        back_populates="incoming_links",
    )

    def __repr__(self) -> str:
        return f"<Link {self.source_id!r} → {self.target_id!r} [{self.link_text!r}]>"
