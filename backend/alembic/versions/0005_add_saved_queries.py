"""Add saved_queries table for Dataview-style dashboards.

Revision ID: 0005
Revises: 0004_add_users
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_saved_queries_name"), "saved_queries", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_queries_name"), table_name="saved_queries")
    op.drop_table("saved_queries")
