"""Multi-user namespace: add owner_id to notes, vault columns to users, shared_vaults table.

Revision ID: 002_multi_user_namespace
Revises:     0005
Create Date: 2026-06-19

What this migration does
------------------------
1. Adds vault_slug, vault_path, vault_display_name to users (if absent).
2. Adds owner_id (FK -> users.id) to notes (if absent).
3. Creates shared_vaults join table (IF NOT EXISTS).
4. Backfills notes.owner_id with the first superuser so legacy notes
   don't become orphaned.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002_multi_user_namespace"
down_revision = "0005"
branch_labels = None
depends_on = None


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------ users
    # Add each vault column only if it doesn't already exist.
    for col, ddl in (
        ("vault_slug", "ALTER TABLE users ADD COLUMN vault_slug VARCHAR(80)"),
        ("vault_path", "ALTER TABLE users ADD COLUMN vault_path TEXT"),
        ("vault_display_name", "ALTER TABLE users ADD COLUMN vault_display_name VARCHAR(200)"),
    ):
        if not _column_exists(conn, "users", col):
            conn.execute(sa.text(ddl))

    conn.execute(
        sa.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_vault_slug ON users (vault_slug)")
    )

    # ------------------------------------------------------------------ notes
    # SQLite ALTER TABLE ADD COLUMN supports a REFERENCES clause but not
    # a named FK constraint — that's fine, the FK is enforced at the ORM layer.
    if not _column_exists(conn, "notes", "owner_id"):
        conn.execute(sa.text("ALTER TABLE notes ADD COLUMN owner_id INTEGER REFERENCES users(id)"))

    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_owner_id ON notes (owner_id)"))

    # --------------------------------------------------------- shared_vaults
    conn.execute(
        sa.text("""
        CREATE TABLE IF NOT EXISTS shared_vaults (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            member_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission  VARCHAR(10) NOT NULL DEFAULT 'read',
            invited_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            accepted_at DATETIME,
            is_active   BOOLEAN NOT NULL DEFAULT 1,
            UNIQUE (owner_id, member_id)
        )
    """)
    )
    conn.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_shared_vaults_owner_id  ON shared_vaults (owner_id)")
    )
    conn.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_shared_vaults_member_id ON shared_vaults (member_id)"
        )
    )

    # ------------------------------------------------------- backfill legacy
    admin_row = conn.execute(
        sa.text("SELECT id FROM users WHERE is_superuser = 1 ORDER BY id LIMIT 1")
    ).fetchone()
    if admin_row:
        admin_id = admin_row[0]
        conn.execute(
            sa.text("UPDATE notes SET owner_id = :uid WHERE owner_id IS NULL"),
            {"uid": admin_id},
        )
        conn.execute(
            sa.text("UPDATE users SET vault_slug = 'admin' WHERE id = :uid AND vault_slug IS NULL"),
            {"uid": admin_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_shared_vaults_member_id"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_shared_vaults_owner_id"))
    conn.execute(sa.text("DROP TABLE IF EXISTS shared_vaults"))
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_notes_owner_id"))
    try:
        conn.execute(sa.text("ALTER TABLE notes DROP COLUMN IF EXISTS owner_id"))
    except Exception:
        pass
    conn.execute(sa.text("DROP INDEX IF EXISTS ix_users_vault_slug"))
    for col in ("vault_display_name", "vault_path", "vault_slug"):
        try:
            conn.execute(sa.text(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}"))
        except Exception:
            pass
