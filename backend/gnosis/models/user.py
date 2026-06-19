"""SQLAlchemy User model — extended for multi-user vault support."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base


class User(Base):
    """User account record.

    Each user has their own isolated vault namespace.  ``vault_path`` is the
    filesystem root where the watcher stores .md files for this user.
    e.g. ``/vaults/ryan`` or ``/data/vaults/alice``.

    ``vault_slug`` is a URL-safe identifier used as the LightRAG working
    directory and as the prefix in shared-vault URLs.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ---- Multi-user additions ----------------------------------------------
    vault_slug: Mapped[Optional[str]] = mapped_column(
        String(80),
        unique=True,
        nullable=True,
        index=True,
        comment="URL-safe identifier used as the vault namespace (e.g. 'ryan')",
    )
    vault_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Absolute filesystem path to this user's vault root (e.g. /vaults/ryan)",
    )
    vault_display_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Human-readable vault name shown in the UI (e.g. 'Ryan\'s KB')",
    )

    # Relationships
    notes: Mapped[list] = relationship(
        "Note",
        back_populates="owner",
        lazy="noload",
        foreign_keys="Note.owner_id",
    )
    shared_vaults_as_owner: Mapped[list] = relationship(
        "SharedVault",
        back_populates="owner",
        foreign_keys="SharedVault.owner_id",
        lazy="noload",
        cascade="all, delete-orphan",
    )
    shared_vault_memberships: Mapped[list] = relationship(
        "SharedVault",
        back_populates="member",
        foreign_keys="SharedVault.member_id",
        lazy="noload",
    )
