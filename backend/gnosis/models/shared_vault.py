"""SharedVault and SharedVaultMember SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base

if TYPE_CHECKING:
    from gnosis.models.user import User


class SharedVault(Base):
    """A vault shared by one owner with one or more members."""

    __tablename__ = "shared_vaults"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="shared_vaults_as_owner",
        foreign_keys=[owner_id],
        lazy="selectin",
    )
    members: Mapped[list["SharedVaultMember"]] = relationship(
        "SharedVaultMember",
        back_populates="vault",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class SharedVaultMember(Base):
    """Association between a SharedVault and a member User."""

    __tablename__ = "shared_vault_members"
    __table_args__ = (
        UniqueConstraint("vault_id", "member_id", name="uq_vault_member"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    vault_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("shared_vaults.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), default="viewer", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    member: Mapped["User"] = relationship(
        "User",
        back_populates="shared_vault_memberships",
        foreign_keys=[member_id],
        lazy="selectin",
    )
    vault: Mapped["SharedVault"] = relationship(
        "SharedVault",
        back_populates="members",
        foreign_keys=[vault_id],
        lazy="selectin",
    )
