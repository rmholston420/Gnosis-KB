"""Note ORM model — the central entity in Gnosis."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.attachment import Attachment
    from gnosis.models.link import Link
    from gnosis.models.tag import Tag


class Note(Base):
    """A single note in the Gnosis vault.

    Notes are stored as plain Markdown files on the filesystem.
    This model is a derived cache of that filesystem state.
    The `vault_path` column is the authoritative link back to the .md file.
    """

    __tablename__ = "notes"

    # Primary key: timestamp-based ID (YYYYMMDD-HHmmss)
    id: Mapped[str] = mapped_column(String(20), primary_key=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Note classification
    note_type: Mapped[str] = mapped_column(
        String(50), default="permanent", index=True
    )  # fleeting | literature | permanent | project | area | resource | journal | moc
    status: Mapped[str] = mapped_column(
        String(50), default="draft", index=True
    )  # draft | in-progress | evergreen

    # Filesystem location
    vault_path: Mapped[str] = mapped_column(String(1000), unique=True)
    folder: Mapped[str] = mapped_column(
        String(100), index=True
    )  # 00-inbox, 10-zettelkasten, etc.

    # Content metadata
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_reviewed: Mapped[Optional[date]] = mapped_column(Date)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Index status
    vector_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    graph_indexed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Raw frontmatter dict (everything from the YAML header)
    frontmatter: Mapped[dict] = mapped_column(JSONB, default=dict)  # type: ignore[type-arg]

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    outgoing_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.target_id",
        back_populates="target",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="note",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Note id={self.id!r} title={self.title!r}>"
