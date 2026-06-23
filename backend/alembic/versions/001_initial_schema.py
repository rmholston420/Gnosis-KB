"""Initial database schema for Gnosis.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-19

This migration is intentionally idempotent: every CREATE TABLE and
CREATE INDEX uses IF NOT EXISTS so it is safe to run against a
database that was pre-populated by SQLAlchemy create_all().
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     VARCHAR(100) NOT NULL UNIQUE,
            email        VARCHAR(255) NOT NULL UNIQUE,
            hashed_password VARCHAR(255) NOT NULL,
            is_active    BOOLEAN NOT NULL DEFAULT 1,
            is_superuser BOOLEAN NOT NULL DEFAULT 0,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS notes (
            id             VARCHAR(20)  PRIMARY KEY,
            title          VARCHAR(500) NOT NULL,
            slug           VARCHAR(500) NOT NULL UNIQUE,
            body           TEXT         NOT NULL DEFAULT '',
            body_html      TEXT         NOT NULL DEFAULT '',
            note_type      VARCHAR(50)  DEFAULT 'permanent',
            status         VARCHAR(50)  DEFAULT 'draft',
            vault_path     VARCHAR(1000) UNIQUE,
            folder         VARCHAR(100),
            source_url     TEXT,
            word_count     INTEGER      DEFAULT 0,
            created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
            modified_at    DATETIME,
            last_reviewed  DATE,
            is_deleted     BOOLEAN      NOT NULL DEFAULT 0,
            vector_indexed BOOLEAN      NOT NULL DEFAULT 0,
            graph_indexed  BOOLEAN      NOT NULL DEFAULT 0,
            frontmatter    TEXT
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_title    ON notes (title)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_slug     ON notes (slug)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_folder   ON notes (folder)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_note_type ON notes (note_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_status   ON notes (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_is_deleted ON notes (is_deleted)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS tags (
            name        VARCHAR(100) PRIMARY KEY,
            description VARCHAR(500) DEFAULT ''
        )
    """)
    )

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id VARCHAR(20)  NOT NULL REFERENCES notes(id)  ON DELETE CASCADE,
            tag_id  VARCHAR(100) NOT NULL REFERENCES tags(name) ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        )
    """)
    )

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS links (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id VARCHAR(20) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_id VARCHAR(20) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            link_text VARCHAR(500) NOT NULL,
            context   TEXT,
            link_type VARCHAR(50) DEFAULT 'wikilink'
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_links_source_id ON links (source_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_links_target_id ON links (target_id)"))

    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS attachments (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id           VARCHAR(20) NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            filename          VARCHAR(500) NOT NULL,
            original_filename VARCHAR(500) NOT NULL,
            file_path         VARCHAR(1000) NOT NULL,
            mime_type         VARCHAR(100) DEFAULT 'application/octet-stream',
            file_size         INTEGER DEFAULT 0,
            extracted_text    TEXT,
            uploaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_attachments_note_id ON attachments (note_id)")
    )


def downgrade() -> None:
    conn = op.get_bind()
    for tbl in ("attachments", "links", "note_tags", "tags", "notes", "users"):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tbl}"))
