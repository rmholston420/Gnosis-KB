"""Note model — extended with owner_id for multi-user vault support."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
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
    All relationships use ``lazy='select'`` (explicit load only).  Every
    router query site that needs a relationship calls
    ``.options(selectinload(...))`` explicitly.

    Using ``lazy='selectin'`` on *any* relationship caused a double-load
    collision: when selectinload(Note.tags) fired, SQLAlchemy also
    auto-fired every ``lazy='selectin'`` relationship on the same Note
    instance.  ``review_card`` (uselist=False) received multiple rows from
    the tag JOIN and raised:

        SAWarning: Multiple rows returned with uselist=False for
        eagerly-loaded attribute 'Note.tags'

    That collision also collapsed Note.tags to a scalar, making the
    create/update endpoints return ``tags: []``.  Setting all relationships
    to ``lazy='select'`` suppresses the automatic sub-SELECTs.
    """

    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note_type: Mapped[str] = mapped_column(String(50), default="permanent", index=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    vault_path: Mapped[str | None] = mapped_column(String(1000), unique=True, nullable=True)
    folder: Mapped[str | None] = mapped_column(String(100), index=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_reviewed: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    vector_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    graph_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    frontmatter: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=True,
    )

    # ---- Multi-user: owner FK ----------------------------------------------
    owner_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,   # nullable so legacy rows survive; migration backfills admin
        index=True,
        comment="FK to users.id — the user who owns this note",
    )

    # Relationships
    # All lazy='select': never auto-load in the background.
    # Routers that need a relationship add .options(selectinload(...)) explicitly.
    # See class docstring for why lazy='selectin' caused tag-list corruption.
    owner: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="notes",
        foreign_keys=[owner_id],
        lazy="noload",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="select",
    )
    outgoing_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source_note",
        lazy="select",
        cascade="all, delete-orphan",
    )
    incoming_links: Mapped[list["Link"]] = relationship(
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
        lazy="select",          # was 'selectin' — caused SAWarning + tags=[] bug
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="note",
        cascade="all, delete-orphan",
        lazy="select",          # was 'selectin' — fired automatically alongside review_card
    )
