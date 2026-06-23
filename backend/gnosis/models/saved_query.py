"""SQLAlchemy model for named Dataview-style query dashboards."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base


class SavedQuery(Base):
    """A persisted Dataview-style query with a user-defined name.

    Ownership
    ---------
    Each SavedQuery belongs to the user who created it via ``owner_id``.
    The column is nullable so dashboards created before multi-user support
    was added remain usable (they appear only to superusers until claimed).
    On DELETE of the owning user the column is set to NULL rather than
    cascading a delete, preserving the dashboard content.

    Example query string::

        FROM 10-zettelkasten WHERE status=draft AND tags CONTAINS eeg
        SORT modified DESC LIMIT 20
    """

    __tablename__ = "saved_queries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # owner — nullable FK; ON DELETE SET NULL preserves the dashboard row
    owner_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        default=None,
    )
    # Lazy relationship — only loaded when explicitly accessed
    owner: Mapped[object | None] = relationship(
        "User", foreign_keys=[owner_id], lazy="select"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
