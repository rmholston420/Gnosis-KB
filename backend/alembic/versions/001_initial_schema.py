"""Initial database schema for Gnosis.

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables."""
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # notes
    op.create_table(
        "notes",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True, nullable=False),
        sa.Column("body", sa.Text, nullable=False, default=""),
        sa.Column("body_html", sa.Text, nullable=False, default=""),
        sa.Column("note_type", sa.String(50), default="permanent"),
        sa.Column("status", sa.String(50), default="draft"),
        sa.Column("vault_path", sa.String(1000), unique=True),
        sa.Column("folder", sa.String(100)),
        sa.Column("source_url", sa.Text),
        sa.Column("word_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("modified_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column("last_reviewed", sa.Date),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("vector_indexed", sa.Boolean, default=False, nullable=False),
        sa.Column("graph_indexed", sa.Boolean, default=False, nullable=False),
        sa.Column("frontmatter", JSONB, default=dict),
    )
    op.create_index("ix_notes_title", "notes", ["title"])
    op.create_index("ix_notes_slug", "notes", ["slug"])
    op.create_index("ix_notes_folder", "notes", ["folder"])
    op.create_index("ix_notes_note_type", "notes", ["note_type"])
    op.create_index("ix_notes_status", "notes", ["status"])
    op.create_index("ix_notes_is_deleted", "notes", ["is_deleted"])

    # tags
    op.create_table(
        "tags",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("description", sa.String(500), default=""),
    )

    # note_tags (association)
    op.create_table(
        "note_tags",
        sa.Column("note_id", sa.String(20), sa.ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(100), sa.ForeignKey("tags.name", ondelete="CASCADE"), primary_key=True),
    )

    # links
    op.create_table(
        "links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(20), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.String(20), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("link_text", sa.String(500), nullable=False),
        sa.Column("context", sa.Text),
        sa.Column("link_type", sa.String(50), default="wikilink"),
    )
    op.create_index("ix_links_source_id", "links", ["source_id"])
    op.create_index("ix_links_target_id", "links", ["target_id"])

    # attachments
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("note_id", sa.String(20), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("mime_type", sa.String(100), default="application/octet-stream"),
        sa.Column("file_size", sa.Integer, default=0),
        sa.Column("extracted_text", sa.Text),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_attachments_note_id", "attachments", ["note_id"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("attachments")
    op.drop_table("links")
    op.drop_table("note_tags")
    op.drop_table("tags")
    op.drop_table("notes")
    op.drop_table("users")
