"""Add full-text search column.

Revision ID: 0003
Revises:     0002
Create Date: 2026-06-19

Adds a search_vector column to notes.
On SQLite: plain TEXT (FTS handled at application layer).
On PostgreSQL: tsvector with GIN index and auto-update trigger.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE notes ADD COLUMN IF NOT EXISTS search_vector tsvector"
        ))
        conn.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notes_search_vector"
            " ON notes USING GIN(search_vector)"
        ))
        conn.execute(sa.text("""
            CREATE OR REPLACE FUNCTION notes_search_vector_update()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(NEW.body,  '')), 'B');
                RETURN NEW;
            END;
            $$;
        """))
        conn.execute(sa.text("""
            DROP TRIGGER IF EXISTS notes_search_vector_trigger ON notes;
            CREATE TRIGGER notes_search_vector_trigger
            BEFORE INSERT OR UPDATE ON notes
            FOR EACH ROW EXECUTE FUNCTION notes_search_vector_update();
        """))
    else:
        # SQLite: add plain TEXT column if not already present
        if not _column_exists(conn, "notes", "search_vector"):
            conn.execute(sa.text(
                "ALTER TABLE notes ADD COLUMN search_vector TEXT"
            ))


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(sa.text(
            "DROP TRIGGER IF EXISTS notes_search_vector_trigger ON notes"
        ))
        conn.execute(sa.text(
            "DROP FUNCTION IF EXISTS notes_search_vector_update"
        ))
        conn.execute(sa.text(
            "DROP INDEX IF EXISTS ix_notes_search_vector"
        ))
    # SQLite: DROP COLUMN requires 3.35+; skip silently on older versions
    try:
        conn.execute(sa.text(
            "ALTER TABLE notes DROP COLUMN IF EXISTS search_vector"
        ))
    except Exception:
        pass
