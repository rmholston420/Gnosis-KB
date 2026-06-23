"""Unit tests for gnosis/routers/ingest.py.

Covers helpers (_timestamp_id, _sanitize_filename, _build_literature_note,
_write_vault_note, _ai_enrich) and the three endpoints:
  POST /ingest/file  — parse dispatch, 400/413/415/422, happy path
  POST /ingest/url   — happy path, 422 on scrape error
  POST /ingest/batch — imported / skipped / error paths, 415/413/422
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: minimal ParsedDocument stand-in
# ---------------------------------------------------------------------------
from gnosis.services.document_parser import ParsedDocument


def _parsed(title="My Doc", text="Some body text.", fmt="pdf") -> ParsedDocument:
    return ParsedDocument(
        title=title,
        text=text,
        raw_format=fmt,
        source="test.pdf",
        page_count=1,
    )


# ---------------------------------------------------------------------------
# _timestamp_id
# ---------------------------------------------------------------------------


def test_timestamp_id_format():
    from gnosis.routers.ingest import _timestamp_id

    tid = _timestamp_id()
    assert len(tid) == 14
    assert tid.isdigit()


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_filename_removes_special_chars():
    from gnosis.routers.ingest import _sanitize_filename

    assert _sanitize_filename("Hello World!") == "hello-world"


def test_sanitize_filename_handles_empty():
    from gnosis.routers.ingest import _sanitize_filename

    assert _sanitize_filename("") == "untitled"


def test_sanitize_filename_truncates_at_80():
    from gnosis.routers.ingest import _sanitize_filename

    long = "a" * 100
    assert len(_sanitize_filename(long)) == 80


# ---------------------------------------------------------------------------
# _build_literature_note
# ---------------------------------------------------------------------------


def test_build_literature_note_contains_required_fields():
    from gnosis.routers.ingest import _build_literature_note

    md = _build_literature_note(
        note_id="20260101120000",
        title="Test Title",
        summary="Short summary.",
        full_text="Full body text.",
        source="source.pdf",
        tags=["tag1", "tag2"],
    )
    assert 'id: "20260101120000"' in md
    assert 'title: "Test Title"' in md
    assert "type: literature" in md
    assert "tag1" in md
    assert "Short summary." in md
    assert "Full body text." in md


def test_build_literature_note_truncates_long_text():
    from gnosis.routers.ingest import _build_literature_note

    long_text = "x" * 10000
    md = _build_literature_note("id", "T", "s", long_text, "src", [])
    assert "..." in md


# ---------------------------------------------------------------------------
# _write_vault_note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_vault_note_creates_file(tmp_path):
    from gnosis.routers.ingest import _write_vault_note

    with patch("gnosis.routers.ingest.settings") as mock_settings:
        mock_settings.vault_path = str(tmp_path)
        rel_path = await _write_vault_note("20260101", "My Title", "70-sources", "# Content")
    assert rel_path.startswith("70-sources/")
    assert rel_path.endswith(".md")
    written = (tmp_path / rel_path).read_text()
    assert "# Content" in written


# ---------------------------------------------------------------------------
# _ai_enrich
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_enrich_returns_parsed_values_when_llm_unavailable():
    from gnosis.routers.ingest import _ai_enrich

    mock_llm = MagicMock()
    mock_llm.is_available = False
    with patch("gnosis.routers.ingest.llm_provider", mock_llm):
        title, summary, tags = await _ai_enrich(_parsed(title="Raw Title", text="Body."))
    assert title == "Raw Title"
    assert "Body" in summary
    assert tags == []


@pytest.mark.asyncio
async def test_ai_enrich_uses_llm_json_response():
    from gnosis.routers.ingest import _ai_enrich

    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.complete = AsyncMock(
        return_value='{"title": "AI Title", "summary": "AI Summary", "tags": ["ai"]}'
    )
    with patch("gnosis.routers.ingest.llm_provider", mock_llm):
        title, summary, tags = await _ai_enrich(_parsed())
    assert title == "AI Title"
    assert summary == "AI Summary"
    assert tags == ["ai"]


@pytest.mark.asyncio
async def test_ai_enrich_falls_back_on_malformed_json():
    from gnosis.routers.ingest import _ai_enrich

    mock_llm = MagicMock()
    mock_llm.is_available = True
    mock_llm.complete = AsyncMock(return_value="Not JSON at all")
    with patch("gnosis.routers.ingest.llm_provider", mock_llm):
        title, summary, tags = await _ai_enrich(_parsed(title="Fallback"))
    assert title == "Fallback"


# ---------------------------------------------------------------------------
# POST /ingest/file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_file_rejects_missing_filename():
    from fastapi import HTTPException

    from gnosis.routers.ingest import ingest_file

    upload = MagicMock()
    upload.filename = ""
    with pytest.raises(HTTPException) as exc_info:
        await ingest_file(file=upload, session=AsyncMock(), _current_user=MagicMock())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_ingest_file_rejects_unsupported_extension():
    from fastapi import HTTPException

    from gnosis.routers.ingest import ingest_file

    upload = MagicMock()
    upload.filename = "archive.zip"
    with pytest.raises(HTTPException) as exc_info:
        await ingest_file(file=upload, session=AsyncMock(), _current_user=MagicMock())
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_ingest_file_rejects_oversized_file():
    from fastapi import HTTPException

    from gnosis.routers.ingest import _MAX_FILE_SIZE, ingest_file

    upload = MagicMock()
    upload.filename = "big.pdf"
    upload.read = AsyncMock(return_value=b"x" * (_MAX_FILE_SIZE + 2))
    with pytest.raises(HTTPException) as exc_info:
        await ingest_file(file=upload, session=AsyncMock(), _current_user=MagicMock())
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_ingest_file_returns_422_on_parse_error():
    from fastapi import HTTPException

    from gnosis.routers.ingest import ingest_file

    upload = MagicMock()
    upload.filename = "broken.pdf"
    upload.read = AsyncMock(return_value=b"%PDF fake")
    with (
        patch("gnosis.routers.ingest.parse_file", side_effect=ValueError("bad pdf")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await ingest_file(file=upload, session=AsyncMock(), _current_user=MagicMock())
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_ingest_file_happy_path(tmp_path):
    from gnosis.routers.ingest import ingest_file

    upload = MagicMock()
    upload.filename = "paper.pdf"
    upload.read = AsyncMock(return_value=b"%PDF")

    mock_llm = MagicMock()
    mock_llm.is_available = False

    with (
        patch("gnosis.routers.ingest.parse_file", return_value=_parsed("My Paper", "Body text")),
        patch("gnosis.routers.ingest.llm_provider", mock_llm),
        patch("gnosis.routers.ingest.settings") as mock_cfg,
    ):
        mock_cfg.vault_path = str(tmp_path)
        resp = await ingest_file(file=upload, session=AsyncMock(), _current_user=MagicMock())

    assert resp.title == "My Paper"
    assert resp.vault_path.startswith("70-sources/")
    assert resp.note_id.isdigit()


# ---------------------------------------------------------------------------
# POST /ingest/url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_url_happy_path(tmp_path):
    from gnosis.routers.ingest import UrlIngestRequest, ingest_url

    mock_llm = MagicMock()
    mock_llm.is_available = False

    # parse_url is imported inside the function body, so patch the module it lives in
    with (
        patch(
            "gnosis.services.document_parser.parse_url",
            AsyncMock(return_value=_parsed("Web Page", "Content", "url")),
        ),
        patch("gnosis.routers.ingest.llm_provider", mock_llm),
        patch("gnosis.routers.ingest.settings") as mock_cfg,
    ):
        mock_cfg.vault_path = str(tmp_path)
        resp = await ingest_url(
            req=UrlIngestRequest(url="https://example.com"),
            session=AsyncMock(),
            _current_user=MagicMock(),
        )

    assert resp.title == "Web Page"
    assert resp.source_url == "https://example.com"


@pytest.mark.asyncio
async def test_ingest_url_returns_422_on_scrape_failure():
    from fastapi import HTTPException

    from gnosis.routers.ingest import UrlIngestRequest, ingest_url

    with (
        patch(
            "gnosis.services.document_parser.parse_url",
            AsyncMock(side_effect=RuntimeError("timeout")),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await ingest_url(
            req=UrlIngestRequest(url="https://bad.example"),
            session=AsyncMock(),
            _current_user=MagicMock(),
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# POST /ingest/batch
# ---------------------------------------------------------------------------


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Build an in-memory zip with the given filename -> content map."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_ingest_batch_rejects_non_zip():
    from fastapi import HTTPException

    from gnosis.routers.ingest import ingest_batch

    upload = MagicMock()
    upload.filename = "notes.tar.gz"
    upload.read = AsyncMock(return_value=b"garbage")
    with pytest.raises(HTTPException) as exc_info:
        await ingest_batch(file=upload, _current_user=MagicMock())
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_ingest_batch_rejects_bad_zip():
    from fastapi import HTTPException

    from gnosis.routers.ingest import ingest_batch

    upload = MagicMock()
    upload.filename = "notes.zip"
    upload.read = AsyncMock(return_value=b"not a zip")
    with pytest.raises(HTTPException) as exc_info:
        await ingest_batch(file=upload, _current_user=MagicMock())
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_ingest_batch_imports_md_files(tmp_path):
    from gnosis.routers.ingest import ingest_batch

    zipped = _make_zip({"note1.md": b"# Hello", "note2.md": b"# World"})
    upload = MagicMock()
    upload.filename = "export.zip"
    upload.read = AsyncMock(return_value=zipped)
    with patch("gnosis.routers.ingest.settings") as mock_cfg:
        mock_cfg.vault_path = str(tmp_path)
        resp = await ingest_batch(file=upload, _current_user=MagicMock())
    assert resp.imported == 2
    assert resp.skipped == 0
    assert resp.errors == 0
    assert resp.total == 2


@pytest.mark.asyncio
async def test_ingest_batch_skips_non_md_entries(tmp_path):
    from gnosis.routers.ingest import ingest_batch

    zipped = _make_zip({"note.md": b"# Note", "image.png": b"\x89PNG"})
    upload = MagicMock()
    upload.filename = "mixed.zip"
    upload.read = AsyncMock(return_value=zipped)
    with patch("gnosis.routers.ingest.settings") as mock_cfg:
        mock_cfg.vault_path = str(tmp_path)
        resp = await ingest_batch(file=upload, _current_user=MagicMock())
    assert resp.imported == 1
    assert resp.skipped == 1


@pytest.mark.asyncio
async def test_ingest_batch_skips_already_existing_file(tmp_path):
    from gnosis.routers.ingest import ingest_batch

    # Pre-create the file so it already exists
    inbox = tmp_path / "00-inbox"
    inbox.mkdir()
    (inbox / "existing.md").write_text("old content")

    zipped = _make_zip({"existing.md": b"# New"})
    upload = MagicMock()
    upload.filename = "dup.zip"
    upload.read = AsyncMock(return_value=zipped)
    with patch("gnosis.routers.ingest.settings") as mock_cfg:
        mock_cfg.vault_path = str(tmp_path)
        resp = await ingest_batch(file=upload, _current_user=MagicMock())
    assert resp.skipped == 1
    assert resp.imported == 0
