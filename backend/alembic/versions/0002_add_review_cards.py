"""Superseded by 001_initial_schema.py — kept as empty stub so Alembic
does not error if this revision ID is referenced in an existing DB's
alembic_version table.

Revision ID: 0002
Revises:     001_initial
Create Date: 2026-06-19 (stub)
"""

from __future__ import annotations

revision = "0002"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # all tables created in 001_initial


def downgrade() -> None:
    pass
