"""Attachment ORM model — files attached to notes."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.note import Note


class Attachment(Base):
    """A file attachment associated with a note.

    Stores metadata about files (PDFs, images, etc.) that were ingested
    and linked to a note. The actual file content is stored on disk.
    """

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), index=True
    )

    filename: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1000))
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    file_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)  # OCR / parsed text

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    note: Mapped["Note"] = relationship("Note", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<Attachment id={self.id} filename={self.filename!r}>"
