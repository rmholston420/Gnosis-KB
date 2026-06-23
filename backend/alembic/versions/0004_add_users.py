"""Add users table (auth layer).

Revision ID: 0004
Revises:     0003
Create Date: 2026-06-19

No-op when the users table already exists (created by 001_initial
or by SQLAlchemy create_all).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # users was already created in 001_initial; this is a safety net.
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        VARCHAR(100) NOT NULL UNIQUE,
            email           VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            full_name       VARCHAR(255),
            is_active       BOOLEAN NOT NULL DEFAULT 1,
            is_superuser    BOOLEAN NOT NULL DEFAULT 0,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_email    ON users (email)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)"))


def downgrade() -> None:
    pass  # users is owned by 001_initial; downgrade there
