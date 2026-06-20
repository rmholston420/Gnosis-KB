"""Note model — extended with owner_id for multi-user vault support."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.attachment import Attachment
    from gnosis.models.review import ReviewCard
    from gnosis.models.user import User


class Note(Base):
    """A single note in the Gnosis vault.

    Multi-user changes:
      - ``owner_id`` FK to ``users.id`` (nullable so existing rows survive migration).
      - All note queries in routers must filter ``Note.owner_id == current_user.id``.
        The helper ``_scoped_notes(session, user_id)`` enforces this.

    The primary key is a timestamp-based ID (e.g., '20260619-143022').
    Notes are never hard-deleted; is_deleted=True marks them as deleted.

    Relationship loading strategy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``Note.tags`` and ``Note.outgoing_links`` / ``Note.incoming_links`` use
    ``lazy='select'`` (explicit load only).  All router query sites that need
    tags call ``.options(selectinload(Note.tags))`` explicitly.  Using
    ``lazy='selectin'`` here caused a double-load collision: the model-level
    background load fired first, then the explicit selectinload() fired again
    on an already-populated collection, collapsing it to a scalar Tag object
    instead of a list (SQLAlchemy SAWarning: 'Multiple rows returned with
    uselist=False').  ``lazy='select'`` suppresses the background load.
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
    frontmatter: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=True,
    )

    # ---- Multi-user: owner FK ----------------------------------------------
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,   # nullable so legacy rows survive; migration backfills admin
        index=True,
        comment="FK to users.id — the user who owns this note",
    )

    # Relationships
    owner: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="notes",
        foreign_keys=[owner_id],
        lazy="noload",
    )
    # lazy='select': do NOT auto-load in background.  All query sites that
    # need tags use .options(selectinload(Note.tags)) explicitly.  A
    # lazy='selectin' here caused a double-load collision with those explicit
    # options, collapsing the list to a scalar on the second pass.
    tags: Mapped[list] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="select",
    )
    outgoing_links: Mapped[list] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source_note",
        lazy="select",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list] = relationship(
        "Link",
        foreign_keys="Link.target_id",
        back_populates="target_note",
        lazy="select",
    )
    review_card: Mapped[Optional["ReviewCard"]] = relationship(
        "ReviewCard",
        back_populates="note",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
