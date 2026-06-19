"""Add owner_id to saved_queries.

Revision ID: 003_saved_query_owner
Revises: 002_multi_user_namespace
Create Date: 2026-06-19

Changes
-------
* ADD COLUMN saved_queries.owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL
* CREATE INDEX ix_saved_queries_owner_id
* Backfill: assign existing rows to the first superuser; leave NULL on
  fresh installs where no users exist yet.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_saved_query_owner"
down_revision = "002_multi_user_namespace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add nullable owner_id column
    op.add_column(
        "saved_queries",
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    # 2. Create explicit named index (add_column index=True may not name it)
    op.create_index(
        "ix_saved_queries_owner_id",
        "saved_queries",
        ["owner_id"],
        unique=False,
    )

    # 3. Backfill: assign existing rows to the first superuser
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT id FROM users WHERE is_superuser = true ORDER BY id LIMIT 1"
        )
    ).fetchone()
    if row is not None:
        superuser_id = row[0]
        conn.execute(
            sa.text(
                "UPDATE saved_queries SET owner_id = :uid WHERE owner_id IS NULL"
            ),
            {"uid": superuser_id},
        )


def downgrade() -> None:
    op.drop_index("ix_saved_queries_owner_id", table_name="saved_queries")
    op.drop_column("saved_queries", "owner_id")
