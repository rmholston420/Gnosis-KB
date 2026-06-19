"""Add owner_id to saved_queries.

Revision ID: 003_saved_query_owner
Revises:     002_multi_user_namespace
Create Date: 2026-06-19

Adds saved_queries.owner_id FK -> users.id ON DELETE SET NULL.
Idempotent: skips the ALTER if the column already exists.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_saved_query_owner"
down_revision = "002_multi_user_namespace"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "sqlite":
        if not _column_exists(conn, "saved_queries", "owner_id"):
            conn.execute(sa.text(
                "ALTER TABLE saved_queries ADD COLUMN owner_id INTEGER"
                " REFERENCES users(id) ON DELETE SET NULL"
            ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_saved_queries_owner_id"
            " ON saved_queries (owner_id)"
        ))
    else:
        # Postgres: use batch for proper FK + named index
        with op.batch_alter_table("saved_queries") as batch:
            batch.add_column(
                sa.Column(
                    "owner_id", sa.Integer,
                    sa.ForeignKey("users.id", ondelete="SET NULL",
                                  name="fk_saved_queries_owner_id"),
                    nullable=True,
                )
            )
        op.create_index(
            "ix_saved_queries_owner_id", "saved_queries", ["owner_id"], unique=False
        )

    # Backfill existing rows to the first superuser
    row = conn.execute(
        sa.text("SELECT id FROM users WHERE is_superuser = 1 ORDER BY id LIMIT 1")
    ).fetchone()
    if row:
        conn.execute(
            sa.text("UPDATE saved_queries SET owner_id = :uid WHERE owner_id IS NULL"),
            {"uid": row[0]},
        )


def downgrade() -> None:
    conn = op.get_bind()
    try:
        conn.execute(sa.text(
            "DROP INDEX IF EXISTS ix_saved_queries_owner_id"
        ))
        conn.execute(sa.text(
            "ALTER TABLE saved_queries DROP COLUMN IF EXISTS owner_id"
        ))
    except Exception:
        pass
