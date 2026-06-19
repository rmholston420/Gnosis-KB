"""SQLAlchemy model for named Dataview-style query dashboards."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from gnosis.database import Base


class SavedQuery(
    Base,
):
    """A persisted Dataview-style query with a user-defined name.

    Example query string::

        FROM 10-zettelkasten WHERE status=draft AND tags CONTAINS eeg
        SORT modified DESC LIMIT 20
    """

    __tablename__ = "saved_queries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
