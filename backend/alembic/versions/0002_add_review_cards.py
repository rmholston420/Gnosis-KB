"""Add review_cards table.

Revision ID: 0002
Revises:     001_initial
Create Date: 2026-06-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("note_id", sa.String(20), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("easiness", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("last_quality", sa.Integer(), nullable=True),
    )
    op.create_index("ix_review_cards_due_date", "review_cards", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_review_cards_due_date", table_name="review_cards")
    op.drop_table("review_cards")
