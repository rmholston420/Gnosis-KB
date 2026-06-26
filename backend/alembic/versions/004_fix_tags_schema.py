"""Fix tags / note_tags schema to match the ORM models.

The initial migration (001_initial_schema.py) created:
  tags        -- name VARCHAR(100) PRIMARY KEY   (no integer id)
  note_tags   -- tag_id VARCHAR(100) REFERENCES tags(name)

But the Tag ORM model expects:
  tags        -- id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE
  note_tags   -- tag_id INTEGER REFERENCES tags(id)

This mismatch causes every query that touches tags (including the notes
list, note detail, and graph endpoints) to crash with a 500 because
SQLAlchemy tries to insert/select an integer tag_id into a VARCHAR column.

Fix strategy
------------
1. Drop note_tags (child) first to remove the FK constraint.
2. Drop tags.
3. Recreate tags with id SERIAL PRIMARY KEY + name VARCHAR(100) UNIQUE.
4. Recreate note_tags with tag_id INTEGER REFERENCES tags(id).

All three steps use IF NOT EXISTS / IF EXISTS so the migration is safe
to re-run on a partially migrated database.

Revision ID: 004_fix_tags_schema
Revises:     003_saved_query_owner
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "004_fix_tags_schema"
down_revision: str = "003_saved_query_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: drop child table that references tags
    conn.execute(sa.text("DROP TABLE IF EXISTS note_tags CASCADE"))

    # Step 2: drop tags (now has no dependents)
    conn.execute(sa.text("DROP TABLE IF EXISTS tags CASCADE"))

    # Step 3: recreate tags with correct schema
    conn.execute(
        sa.text("""
        CREATE TABLE tags (
            id    SERIAL       PRIMARY KEY,
            name  VARCHAR(100) NOT NULL UNIQUE
        )
        """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_tags_name ON tags (name)"))

    # Step 4: recreate note_tags with INTEGER tag_id FK
    conn.execute(
        sa.text("""
        CREATE TABLE note_tags (
            note_id  VARCHAR(20) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id   INTEGER     NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        )
        """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_note_tags_note_id ON note_tags (note_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_note_tags_tag_id  ON note_tags (tag_id)"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS note_tags CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS tags CASCADE"))
    # Restore the (broken) original schema so downgrade is consistent
    conn.execute(
        sa.text("""
        CREATE TABLE tags (
            name        VARCHAR(100) PRIMARY KEY,
            description VARCHAR(500) DEFAULT ''
        )
        """)
    )
    conn.execute(
        sa.text("""
        CREATE TABLE note_tags (
            note_id VARCHAR(20)  NOT NULL REFERENCES notes(id)   ON DELETE CASCADE,
            tag_id  VARCHAR(100) NOT NULL REFERENCES tags(name)  ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        )
        """)
    )
