"""SharedVault model — many-to-many vault access grants.

A SharedVault row means: *owner* grants *member* read (or write) access
to the owner's vault namespace.

Permission levels
-----------------
read  — member can view notes, use chat/search, generate MOCs
write — member can also create/edit/delete notes in the owner's vault
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gnosis.database import Base


class SharedVault(Base):
    """Represents one user granting another user access to their vault."""

    __tablename__ = "shared_vaults"
    __table_args__ = (
        UniqueConstraint("owner_id", "member_id", name="uq_shared_vault_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="read",
        comment="'read' or 'write'",
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="shared_vaults_as_owner",
        foreign_keys=[owner_id],
        lazy="selectin",
    )
    member: Mapped["User"] = relationship(
        "User",
        back_populates="shared_vault_memberships",
        foreign_keys=[member_id],
        lazy="selectin",
    )

    @property
    def can_write(self) -> bool:
        return self.permission == "write" and self.is_active
