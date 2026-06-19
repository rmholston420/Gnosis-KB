"""Tests for export router."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vault_zip_empty(client: AsyncClient) -> None:
    """Export endpoint returns a zip even when the vault is empty."""
    resp = await client.get("/api/v1/export/vault.zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"


@pytest.mark.asyncio
async def test_export_note_not_found(client: AsyncClient) -> None:
    """Export single note returns 404 for nonexistent ID."""
    resp = await client.get("/api/v1/export/note/nonexistent.md")
    assert resp.status_code == 404
