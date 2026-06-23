"""Tests for the export router.

Covers:
  - GET /api/v1/export/?format=markdown  → zip with .md content
  - GET /api/v1/export/?format=json      → JSON array
  - GET /api/v1/export/vault.zip         → legacy zip alias
  - GET /api/v1/export/note/{id}.md      → single note markdown
  - 404 for nonexistent note
  - 422 for invalid format param
"""

from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_note(client: AsyncClient, title: str = "Export Test Note") -> str:
    """POST a note and return its id."""
    resp = await client.post(
        "/api/v1/notes/",
        json={
            "title": title,
            "body": f"# {title}\n\nBody content here.",
            "folder": "10-zettelkasten",
            "note_type": "permanent",
            "tags": ["export", "test"],
        },
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_markdown_zip_empty(async_client: AsyncClient) -> None:
    """Markdown export returns a valid zip even with no notes."""
    resp = await async_client.get("/api/v1/export/?format=markdown")
    assert resp.status_code == 200
    assert "zip" in resp.headers["content-type"]
    # Verify it's a real zip
    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf) as zf:
        assert isinstance(zf.namelist(), list)


@pytest.mark.asyncio
async def test_export_json_empty(async_client: AsyncClient) -> None:
    """JSON export returns an empty list when no notes exist."""
    resp = await async_client.get("/api/v1/export/?format=json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_export_markdown_contains_note(async_client: AsyncClient) -> None:
    """Markdown zip contains the created note as a .md file."""
    note_id = await _create_note(async_client, "Zip Content Note")
    resp = await async_client.get("/api/v1/export/?format=markdown")
    assert resp.status_code == 200
    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert any(note_id in n or "Zip" in n for n in names), f"Note not in zip: {names}"


@pytest.mark.asyncio
async def test_export_json_contains_note(async_client: AsyncClient) -> None:
    """JSON export includes the created note with expected fields."""
    note_id = await _create_note(async_client, "JSON Export Note")
    resp = await async_client.get("/api/v1/export/?format=json")
    assert resp.status_code == 200
    notes = resp.json()
    ids = [n["id"] for n in notes]
    assert note_id in ids
    # Validate schema
    note = next(n for n in notes if n["id"] == note_id)
    for field in ("id", "title", "body", "folder", "tags", "created_at", "modified_at"):
        assert field in note, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_export_vault_zip_legacy(async_client: AsyncClient) -> None:
    """Legacy /vault.zip endpoint still works."""
    resp = await async_client.get("/api/v1/export/vault.zip")
    assert resp.status_code == 200
    assert "zip" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_export_single_note_md(async_client: AsyncClient) -> None:
    """Single-note markdown download returns 200 with text/markdown."""
    note_id = await _create_note(async_client, "Single Note Export")
    resp = await async_client.get(f"/api/v1/export/note/{note_id}.md")
    assert resp.status_code == 200
    assert "markdown" in resp.headers["content-type"]
    content = resp.text
    assert "---" in content  # frontmatter present
    assert "Single Note Export" in content


@pytest.mark.asyncio
async def test_export_note_not_found(async_client: AsyncClient) -> None:
    """Single-note export returns 404 for nonexistent ID."""
    resp = await async_client.get("/api/v1/export/note/does-not-exist.md")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_export_invalid_format(async_client: AsyncClient) -> None:
    """Invalid format param returns 422 Unprocessable Entity."""
    resp = await async_client.get("/api/v1/export/?format=csv")
    assert resp.status_code == 422
