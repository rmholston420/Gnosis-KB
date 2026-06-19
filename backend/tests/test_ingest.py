"""
Tests for ingest router endpoints.
"""
from __future__ import annotations

import io
import zipfile

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_file_unsupported_format(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ingest/file with unsupported extension returns 415."""
    resp = await client.post(
        "/api/v1/ingest/file",
        headers=auth_headers,
        files={"file": ("test.txt", b"plain text content", "text/plain")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_ingest_batch_not_zip(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ingest/batch with non-zip file returns 415."""
    resp = await client.post(
        "/api/v1/ingest/batch",
        headers=auth_headers,
        files={"file": ("notes.tar.gz", b"fake tar", "application/gzip")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_ingest_batch_valid_zip(client: AsyncClient, auth_headers: dict, tmp_path) -> None:
    """POST /ingest/batch with a valid zip of .md files returns 200."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("note-one.md", "# Note One\n\nHello from batch import.")
        zf.writestr("note-two.md", "# Note Two\n\nAnother test note.")
    buf.seek(0)

    resp = await client.post(
        "/api/v1/ingest/batch",
        headers=auth_headers,
        files={"file": ("batch.zip", buf, "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # May be 'imported' or 'skipped' depending on vault state
    assert data["imported"] + data["skipped"] + data["errors"] == data["total"]


@pytest.mark.asyncio
async def test_ingest_url_invalid(client: AsyncClient, auth_headers: dict) -> None:
    """POST /ingest/url with unreachable URL returns 422."""
    resp = await client.post(
        "/api/v1/ingest/url",
        headers=auth_headers,
        json={"url": "http://localhost:1/nonexistent"},
    )
    assert resp.status_code == 422
