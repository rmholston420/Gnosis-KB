"""Multi-user namespace: add owner_id to notes, vault columns to users, shared_vaults table.

Revision ID: 002_multi_user_namespace
Revises:     0005
Create Date: 2026-06-19

What this migration does
------------------------
1. Adds vault_slug, vault_path, vault_display_name to users.
2. Adds owner_id (FK -> users.id) to notes.
3. Creates shared_vaults join table.
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


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # ------------------------------------------------------------------ users
    # batch_alter_table is safe here: we're only adding nullable columns
    # with no constraints, so SQLite doesn't need to rebuild the table.
    with op.batch_alter_table("users", recreate="never") as batch:
        batch.add_column(sa.Column("vault_slug", sa.String(80), nullable=True))
        batch.add_column(sa.Column("vault_path", sa.Text, nullable=True))
        batch.add_column(sa.Column("vault_display_name", sa.String(200), nullable=True))

    # Unique index on vault_slug (created outside batch to avoid rebuild)
    op.create_index("ix_users_vault_slug", "users", ["vault_slug"], unique=True)

    # ------------------------------------------------------------------ notes
    # SQLite ALTER TABLE ADD COLUMN does not support FOREIGN KEY clauses,
    # but the FK is enforced at the ORM layer and the column itself is just
    # a nullable integer.  Use raw SQL so we avoid batch_alter_table
    # rebuilding the entire table (which would fail on unnamed constraints).
    if dialect == "sqlite":
        conn.execute(sa.text(
            "ALTER TABLE notes ADD COLUMN owner_id INTEGER REFERENCES users(id)"
        ))
    else:
        with op.batch_alter_table("notes") as batch:
            batch.add_column(
                sa.Column(
                    "owner_id",
                    sa.Integer,
                    sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_notes_owner_id"),
                    nullable=True,
                )
            )

    op.create_index("ix_notes_owner_id", "notes", ["owner_id"], unique=False)

    # --------------------------------------------------------- shared_vaults
    op.create_table(
        "shared_vaults",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "owner_id", sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_sv_owner"),
            nullable=False, index=True,
        ),
        sa.Column(
            "member_id", sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_sv_member"),
            nullable=False, index=True,
        ),
        sa.Column("permission", sa.String(10), nullable=False, server_default="read"),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.UniqueConstraint("owner_id", "member_id", name="uq_shared_vault_pair"),
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
            sa.text(
                "UPDATE users SET vault_slug = 'admin'"
                " WHERE id = :uid AND vault_slug IS NULL"
            ),
            {"uid": admin_id},
        )


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_table("shared_vaults")

    try:
        op.drop_index("ix_notes_owner_id", table_name="notes")
    except Exception:
        pass

    # SQLite does not support DROP COLUMN before 3.35; use raw SQL
    # which is a no-op on older versions rather than crashing.
    conn.execute(sa.text(
        "ALTER TABLE notes DROP COLUMN IF EXISTS owner_id"
    ))

    try:
        op.drop_index("ix_users_vault_slug", table_name="users")
    except Exception:
        pass

    with op.batch_alter_table("users", recreate="never") as batch:
        batch.drop_column("vault_display_name")
        batch.drop_column("vault_path")
        batch.drop_column("vault_slug")
