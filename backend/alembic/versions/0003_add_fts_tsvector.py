"""Add full-text search tsvector column and trigger.

Revision ID: 0003
Revises:     0002
Create Date: 2026-06-19

Note: tsvector / GIN index are PostgreSQL-only. On SQLite the column
is added as plain Text so the migration is cross-dialect safe.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        # Add tsvector column and GIN index
        op.add_column("notes", sa.Column("search_vector", sa.Text(), nullable=True))
        bind.execute(sa.text(
            "ALTER TABLE notes ADD COLUMN IF NOT EXISTS search_vector tsvector"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_notes_search_vector "
            "ON notes USING GIN(search_vector)"
        ))
        # Trigger to keep tsvector current
        bind.execute(sa.text("""
            CREATE OR REPLACE FUNCTION notes_search_vector_update() RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(NEW.body, '')), 'B');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        bind.execute(sa.text("""
            DROP TRIGGER IF EXISTS notes_search_vector_trigger ON notes;
            CREATE TRIGGER notes_search_vector_trigger
            BEFORE INSERT OR UPDATE ON notes
            FOR EACH ROW EXECUTE FUNCTION notes_search_vector_update();
        """))
    else:
        # SQLite: plain text column; FTS handled at application layer
        with op.batch_alter_table("notes") as batch:
            batch.add_column(sa.Column("search_vector", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        bind.execute(sa.text(
            "DROP TRIGGER IF EXISTS notes_search_vector_trigger ON notes"
        ))
        bind.execute(sa.text(
            "DROP FUNCTION IF EXISTS notes_search_vector_update"
        ))
        bind.execute(sa.text(
            "DROP INDEX IF EXISTS ix_notes_search_vector"
        ))

    with op.batch_alter_table("notes") as batch:
        batch.drop_column("search_vector")
