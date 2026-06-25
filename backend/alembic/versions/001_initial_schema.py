"""Initial database schema for Gnosis.

Revision ID: 001_initial
Revises:
Create Date: 2026-06-19

This migration is intentionally idempotent: every CREATE TABLE and
CREATE INDEX uses IF NOT EXISTS so it is safe to run against a
database that was pre-populated by SQLAlchemy create_all().

Schema matches current SQLAlchemy models exactly:
  - users           (no `username`; has vault_slug / vault_path / vault_display_name / full_name)
  - notes           (includes owner_id FK)
  - tags / note_tags / links / attachments
  - review_cards
  - saved_queries
  - shared_vaults
  - shared_vault_members

NOTE: Written for PostgreSQL.
  - Auto-increment PKs use SERIAL (not SQLite AUTOINCREMENT)
  - Timestamps use TIMESTAMP (not SQLite DATETIME)
  - Boolean defaults use TRUE/FALSE (not 1/0)
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

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            id                  SERIAL       PRIMARY KEY,
            email               VARCHAR(320) NOT NULL UNIQUE,
            hashed_password     VARCHAR(200) NOT NULL,
            full_name           VARCHAR(200),
            is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
            is_superuser        BOOLEAN      NOT NULL DEFAULT FALSE,
            created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            vault_slug          VARCHAR(80)  UNIQUE,
            vault_path          TEXT,
            vault_display_name  VARCHAR(200)
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_email      ON users (email)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_users_vault_slug ON users (vault_slug)"))

    # ------------------------------------------------------------------
    # notes
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS notes (
            id             VARCHAR(20)   PRIMARY KEY,
            title          VARCHAR(500)  NOT NULL,
            slug           VARCHAR(500)  NOT NULL UNIQUE,
            body           TEXT          NOT NULL DEFAULT '',
            body_html      TEXT          NOT NULL DEFAULT '',
            note_type      VARCHAR(50)   DEFAULT 'permanent',
            status         VARCHAR(50)   DEFAULT 'draft',
            vault_path     VARCHAR(1000) UNIQUE,
            folder         VARCHAR(100),
            source_url     TEXT,
            word_count     INTEGER       DEFAULT 0,
            created_at     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
            modified_at    TIMESTAMP,
            last_reviewed  DATE,
            is_deleted     BOOLEAN       NOT NULL DEFAULT FALSE,
            vector_indexed BOOLEAN       NOT NULL DEFAULT FALSE,
            graph_indexed  BOOLEAN       NOT NULL DEFAULT FALSE,
            frontmatter    TEXT,
            owner_id       INTEGER       REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    )
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_title      ON notes (title)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_slug       ON notes (slug)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_folder     ON notes (folder)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_note_type  ON notes (note_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_status     ON notes (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_is_deleted ON notes (is_deleted)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_owner_id   ON notes (owner_id)"))

    # ------------------------------------------------------------------
    # tags / note_tags
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # links
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS links (
            id        SERIAL      PRIMARY KEY,
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

    # ------------------------------------------------------------------
    # attachments
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS attachments (
            id                SERIAL       PRIMARY KEY,
            note_id           VARCHAR(20)  NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            filename          VARCHAR(500)  NOT NULL,
            original_filename VARCHAR(500)  NOT NULL,
            file_path         VARCHAR(1000) NOT NULL,
            mime_type         VARCHAR(100) DEFAULT 'application/octet-stream',
            file_size         INTEGER      DEFAULT 0,
            extracted_text    TEXT,
            uploaded_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_attachments_note_id ON attachments (note_id)")
    )

    # ------------------------------------------------------------------
    # review_cards
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS review_cards (
            id          VARCHAR(20) PRIMARY KEY,
            note_id     VARCHAR(20) NOT NULL UNIQUE REFERENCES notes(id) ON DELETE CASCADE,
            easiness    REAL        NOT NULL DEFAULT 2.5,
            interval    INTEGER     NOT NULL DEFAULT 1,
            repetitions INTEGER     NOT NULL DEFAULT 0,
            due_date    DATE,
            last_quality INTEGER,
            created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_review_cards_note_id  ON review_cards (note_id)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_review_cards_due_date ON review_cards (due_date)")
    )

    # ------------------------------------------------------------------
    # saved_queries
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS saved_queries (
            id          SERIAL       PRIMARY KEY,
            owner_id    INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        VARCHAR(200) NOT NULL,
            query       TEXT         NOT NULL,
            filters     TEXT,
            created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_saved_queries_owner_id ON saved_queries (owner_id)")
    )

    # ------------------------------------------------------------------
    # shared_vaults
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS shared_vaults (
            id         SERIAL       PRIMARY KEY,
            owner_id   INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name       VARCHAR(200) NOT NULL,
            created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_shared_vaults_owner_id ON shared_vaults (owner_id)")
    )

    # ------------------------------------------------------------------
    # shared_vault_members
    # ------------------------------------------------------------------
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS shared_vault_members (
            id         SERIAL      PRIMARY KEY,
            vault_id   INTEGER     NOT NULL REFERENCES shared_vaults(id) ON DELETE CASCADE,
            member_id  INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission VARCHAR(50) NOT NULL DEFAULT 'viewer',
            created_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (vault_id, member_id)
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_svm_vault_id   ON shared_vault_members (vault_id)")
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_svm_member_id  ON shared_vault_members (member_id)")
    )


def downgrade() -> None:
    conn = op.get_bind()
    for tbl in (
        "shared_vault_members",
        "shared_vaults",
        "saved_queries",
        "review_cards",
        "attachments",
        "links",
        "note_tags",
        "tags",
        "notes",
        "users",
    ):
        conn.execute(sa.text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
