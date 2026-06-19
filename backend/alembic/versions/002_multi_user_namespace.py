"""Multi-user namespace: add owner_id to notes, vault columns to users, shared_vaults table.

Revision ID: 002_multi_user_namespace
Downrev: 001  (update this to match your previous head if different)
Create Date: 2026-06-19

What this migration does
------------------------
1. Adds ``vault_slug``, ``vault_path``, ``vault_display_name`` to ``users``.
2. Adds ``owner_id`` (FK → users.id) to ``notes``.
3. Creates ``shared_vaults`` table.
4. Backfills ``notes.owner_id`` with the first superuser's id so legacy notes
   don't become orphaned after migration.

Rollback removes shared_vaults, drops the owner_id column, and drops the
new user columns.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_multi_user_namespace"
down_revision = None  # set to your current head revision string
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- users: add vault columns -----------------------------------------
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("vault_slug", sa.String(80), nullable=True, unique=True, index=True)
        )
        batch.add_column(sa.Column("vault_path", sa.Text, nullable=True))
        batch.add_column(sa.Column("vault_display_name", sa.String(200), nullable=True))

    # ---- notes: add owner_id FK -------------------------------------------
    with op.batch_alter_table("notes") as batch:
        batch.add_column(
            sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"),
                      nullable=True, index=True)
        )

    # ---- shared_vaults table -----------------------------------------------
    op.create_table(
        "shared_vaults",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("member_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("permission", sa.String(10), nullable=False, server_default="read"),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.UniqueConstraint("owner_id", "member_id", name="uq_shared_vault_pair"),
    )

    # ---- Backfill: assign legacy notes to the first superuser --------------
    conn = op.get_bind()
    admin_row = conn.execute(
        sa.text("SELECT id FROM users WHERE is_superuser = true ORDER BY id LIMIT 1")
    ).fetchone()
    if admin_row:
        admin_id = admin_row[0]
        conn.execute(
            sa.text("UPDATE notes SET owner_id = :uid WHERE owner_id IS NULL"),
            {"uid": admin_id},
        )
        # Also set vault_slug for the admin so their vault path resolves
        conn.execute(
            sa.text("UPDATE users SET vault_slug = 'admin' WHERE id = :uid AND vault_slug IS NULL"),
            {"uid": admin_id},
        )


def downgrade() -> None:
    op.drop_table("shared_vaults")

    with op.batch_alter_table("notes") as batch:
        batch.drop_column("owner_id")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("vault_display_name")
        batch.drop_column("vault_path")
        batch.drop_column("vault_slug")
