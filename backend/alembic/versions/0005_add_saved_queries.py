"""Add saved_queries table for Dataview-style dashboards.

Revision ID: 0005
Revises:     0004
Create Date: 2026-06-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS saved_queries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        VARCHAR(200) NOT NULL UNIQUE,
            query       TEXT         NOT NULL,
            description TEXT         NOT NULL DEFAULT '',
            created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_saved_queries_name"
        " ON saved_queries (name)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_saved_queries_name"))
    conn.execute(sa.text("DROP TABLE IF EXISTS saved_queries"))
