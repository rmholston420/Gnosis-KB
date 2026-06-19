"""Note model."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.review import ReviewCard


class Note(Base):
    """A single note in the Gnosis vault.

    The primary key is a timestamp-based ID (e.g., '20260619-143022').
    Notes are never hard-deleted; is_deleted=True marks them as deleted.

    ``frontmatter`` uses SQLAlchemy's generic ``JSON`` type so the model
    works with both PostgreSQL (stores as jsonb) and SQLite (used in CI).
    PostgreSQL automatically maps JSON columns to jsonb storage; no
    dialect-specific import is needed here.
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note_type: Mapped[str] = mapped_column(String(50), default="permanent", index=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    vault_path: Mapped[Optional[str]] = mapped_column(String(1000), unique=True, nullable=True)
    folder: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_reviewed: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    vector_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    graph_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # JSON (not JSONB) keeps the model dialect-agnostic; PostgreSQL stores
    # it as jsonb anyway.  SQLite CI tests no longer fail on an unknown type.
    frontmatter: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=True,
    )

    # Relationships
    tags: Mapped[list] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="selectin",
    )
    outgoing_links: Mapped[list] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source_note",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list] = relationship(
        "Link",
        foreign_keys="Link.target_id",
        back_populates="target_note",
        lazy="selectin",
    )
    review_card: Mapped[Optional["ReviewCard"]] = relationship(
        "ReviewCard",
        back_populates="note",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
