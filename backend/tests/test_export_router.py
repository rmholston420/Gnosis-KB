"""Tests for gnosis/routers/export.py.

Covers: _iso, _note_to_markdown, _note_to_dict, _fetch_user_notes,
export_vault (markdown + json), export_vault_zip, export_note_md
(found + 404), export_note_pdf (disabled + no weasyprint).
"""
from __future__ import annotations

import json
import zipfile
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag(name="zettelkasten"):
    t = MagicMock()
    t.name = name
    return t


def _note(note_id="n1", title="My Note", body="Body text.", folder="10-zettelkasten"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = folder
    n.note_type = "permanent"
    n.status = "active"
    n.vault_path = f"{folder}/{note_id}.md"
    n.word_count = 2
    n.tags = [_tag("eeg"), _tag("research")]
    n.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    n.modified_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
    return n


def _user(uid=1):
    u = MagicMock()
    u.id = uid
    return u


def _db_notes(notes):
    result = MagicMock()
    result.scalars.return_value.all.return_value = notes
    result.scalar_one_or_none.return_value = notes[0] if notes else None
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_iso_datetime():
    from gnosis.routers.export import _iso
    dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    assert "2025-01-15" in _iso(dt)


def test_iso_date():
    from gnosis.routers.export import _iso
    assert _iso(date(2025, 3, 5)) == "2025-03-05"


def test_iso_none_returns_empty_string():
    from gnosis.routers.export import _iso
    assert _iso(None) == ""


def test_iso_string_passthrough():
    from gnosis.routers.export import _iso
    assert _iso("2025-01-01") == "2025-01-01"


def test_note_to_markdown_contains_frontmatter():
    from gnosis.routers.export import _note_to_markdown
    note = _note()
    md = _note_to_markdown(note)
    assert "---" in md
    assert 'title: "My Note"' in md
    assert "eeg" in md
    assert "Body text." in md


def test_note_to_dict_structure():
    from gnosis.routers.export import _note_to_dict
    note = _note()
    d = _note_to_dict(note)
    assert d["id"] == "n1"
    assert d["title"] == "My Note"
    assert "eeg" in d["tags"]
    assert d["word_count"] == 2


# ---------------------------------------------------------------------------
# _fetch_user_notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_user_notes_returns_list():
    from gnosis.routers.export import _fetch_user_notes
    note = _note()
    db = _db_notes([note])
    result = await _fetch_user_notes(db, owner_id=1)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# GET /export/?format=markdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_vault_markdown_returns_zip():
    from gnosis.routers.export import export_vault
    note = _note()
    db = _db_notes([note])

    response = await export_vault(format="markdown", db=db, current_user=_user())
    # Collect the streaming response body
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
    raw = b"".join(chunks)

    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    assert len(names) == 1
    assert names[0].endswith(".md")


@pytest.mark.asyncio
async def test_export_vault_json_returns_array():
    from gnosis.routers.export import export_vault
    note = _note()
    db = _db_notes([note])

    response = await export_vault(format="json", db=db, current_user=_user())
    data = json.loads(response.body)
    assert isinstance(data, list)
    assert data[0]["title"] == "My Note"


# ---------------------------------------------------------------------------
# GET /export/vault.zip
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_vault_zip_streams_zip():
    from gnosis.routers.export import export_vault_zip
    note = _note()
    db = _db_notes([note])

    response = await export_vault_zip(db=db, current_user=_user())
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
    raw = b"".join(chunks)

    zf = zipfile.ZipFile(io.BytesIO(raw))
    assert len(zf.namelist()) == 1


# ---------------------------------------------------------------------------
# GET /export/note/{id}.md
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_note_md_returns_content():
    from gnosis.routers.export import export_note_md
    note = _note()
    db = _db_notes([note])

    response = await export_note_md(note_id="n1", db=db, current_user=_user())
    content = response.body.decode()
    assert "My Note" in content
    assert "Body text." in content


@pytest.mark.asyncio
async def test_export_note_md_returns_404_when_missing():
    from fastapi import HTTPException
    from gnosis.routers.export import export_note_md
    db = _db_notes([])

    with pytest.raises(HTTPException) as exc_info:
        await export_note_md(note_id="missing", db=db, current_user=_user())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /export/note/{id}.pdf
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_note_pdf_returns_501_when_disabled():
    from fastapi import HTTPException
    from gnosis.routers.export import export_note_pdf

    with patch("gnosis.routers.export.settings") as mock_settings:
        mock_settings.enable_pdf_export = False
        with pytest.raises(HTTPException) as exc_info:
            await export_note_pdf(note_id="n1", db=AsyncMock(), current_user=_user())
    assert exc_info.value.status_code == 501


@pytest.mark.asyncio
async def test_export_note_pdf_returns_501_when_weasyprint_missing():
    from fastapi import HTTPException
    from gnosis.routers.export import export_note_pdf

    with patch("gnosis.routers.export.settings") as mock_settings:
        mock_settings.enable_pdf_export = True
        with patch("builtins.__import__", side_effect=ImportError("no weasyprint")):
            # builtins.__import__ patching is broad; use a targeted approach
            pass

    # More targeted: patch the import inside the function
    with patch("gnosis.routers.export.settings") as mock_settings:
        mock_settings.enable_pdf_export = True
        import sys
        # Temporarily remove weasyprint from sys.modules if present
        weasyprint_backup = sys.modules.pop("weasyprint", None)
        try:
            with pytest.raises(HTTPException) as exc_info:
                await export_note_pdf(note_id="n1", db=AsyncMock(), current_user=_user())
            assert exc_info.value.status_code == 501
        finally:
            if weasyprint_backup is not None:
                sys.modules["weasyprint"] = weasyprint_backup


import io  # noqa: E402  (used by streaming response tests above)
