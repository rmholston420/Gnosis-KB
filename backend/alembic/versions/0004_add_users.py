"""Superseded by 001_initial_schema.py — no-op stub.
The old version created a `username` column that no longer exists in the
User model; replaced by email-only auth.

Revision ID: 0004
Revises:     0003
Create Date: 2026-06-19 (stub)
"""

from __future__ import annotations

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # users table is fully created in 001_initial


def downgrade() -> None:
    pass
