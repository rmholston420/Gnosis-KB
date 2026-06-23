"""Note SQLAlchemy model."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.link import Link
    from gnosis.models.review import ReviewCard
    from gnosis.models.tag import Tag


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_reviewed: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="note_tags",
        back_populates="notes",
        lazy="selectin",
    )

    outgoing_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.source_id",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    incoming_links: Mapped[list["Link"]] = relationship(
        "Link",
        foreign_keys="Link.target_id",
        back_populates="target",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    review_card: Mapped["ReviewCard | None"] = relationship(
        "ReviewCard",
        back_populates="note",
        uselist=False,
        # noload: never auto-load the review card when fetching notes.
        # The review router loads it explicitly via _get_card_or_404.
        # Using selectin or joined here caused a conflict with the
        # eagerly-loaded attribute 'Note.tags' which collapsed Note.tags
        # to a scalar and broke the tags API response.
        lazy="noload",
    )
