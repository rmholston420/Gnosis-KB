"""Superseded by 001_initial_schema.py — no-op stub.
All multi-user columns (vault_slug, vault_path, vault_display_name,
owner_id on notes, shared_vaults, shared_vault_members) are created
directly in 001_initial.

Revision ID: 002_multi_user_namespace
Revises:     0005
Create Date: 2026-06-19 (stub)
"""
from __future__ import annotations
revision = "002_multi_user_namespace"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
