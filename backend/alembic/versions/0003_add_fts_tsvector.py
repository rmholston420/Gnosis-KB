"""Add tsvector column + GIN index + auto-update trigger to notes table.

Revision ID: 0003_add_fts_tsvector
Revises: 0002_add_review_cards
Create Date: 2026-06-19

Strategy
--------
A generated column would be ideal but SQLAlchemy/Alembic don't expose it
portably, so we use a BEFORE INSERT/UPDATE trigger instead.  The trigger
concat-weights title (A), folder (C), body (B) into a single tsvector so
ranking rewards title matches most.

The GIN index makes tsvector queries fast (sub-10ms for tens of thousands
of notes).  The @@ operator used in the search service hits this index.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_add_fts_tsvector"
down_revision = "0002_add_review_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add the tsvector column
    op.add_column(
        "notes",
        sa.Column(
            "fts",
            sa.types.UserDefinedType(),  # tsvector is PG-native; use raw DDL
            nullable=True,
        ),
    )

    # 2. Swap the column type to tsvector via raw DDL
    op.execute("ALTER TABLE notes ALTER COLUMN fts TYPE tsvector USING fts::tsvector")

    # 3. Back-fill all existing rows
    op.execute("""
        UPDATE notes
        SET fts =
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(folder, '')), 'C') ||
            setweight(to_tsvector('english', coalesce(body,  '')), 'B')
    """)

    # 4. GIN index for fast @@ queries
    op.create_index(
        "ix_notes_fts",
        "notes",
        ["fts"],
        postgresql_using="gin",
    )

    # 5. Trigger function: keep fts in sync on every write
    op.execute("""
        CREATE OR REPLACE FUNCTION notes_fts_update() RETURNS trigger AS $$
        BEGIN
            NEW.fts :=
                setweight(to_tsvector('english', coalesce(NEW.title,  '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.folder, '')), 'C') ||
                setweight(to_tsvector('english', coalesce(NEW.body,   '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER notes_fts_trigger
        BEFORE INSERT OR UPDATE OF title, folder, body
        ON notes
        FOR EACH ROW
        EXECUTE FUNCTION notes_fts_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS notes_fts_trigger ON notes")
    op.execute("DROP FUNCTION IF EXISTS notes_fts_update")
    op.drop_index("ix_notes_fts", table_name="notes")
    op.drop_column("notes", "fts")
