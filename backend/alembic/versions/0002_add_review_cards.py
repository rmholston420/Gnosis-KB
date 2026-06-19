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
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS review_cards (
            note_id     VARCHAR(20) NOT NULL PRIMARY KEY
                        REFERENCES notes(id) ON DELETE CASCADE,
            easiness    FLOAT   NOT NULL DEFAULT 2.5,
            interval    INTEGER NOT NULL DEFAULT 1,
            repetitions INTEGER NOT NULL DEFAULT 0,
            due_date    DATE    NOT NULL,
            last_quality INTEGER
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_review_cards_due_date"
        " ON review_cards (due_date)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_review_cards_due_date"))
    conn.execute(sa.text("DROP TABLE IF EXISTS review_cards"))
