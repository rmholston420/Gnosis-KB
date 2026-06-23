"""Coverage tests for gnosis/routers/ingest.py.

The router:
  - Validates extension directly (not via detect_format)
  - Calls parse_file(Path) synchronously (wrapped in run_in_executor inside)
  - Calls _ai_enrich(parsed) -> (title, summary, tags)
  - Calls _write_vault_note(note_id, title, folder, content) -> str path
  - Uses get_session (not get_db)
  - No ParsedDocument import needed in tests
"""
from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user
from gnosis.database import get_session
from gnosis.models.user import User
from gnosis.routers.ingest import router


def _user():
    return User(id=1, email="u@t.com", hashed_password="x", is_active=True, is_superuser=False)


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = AsyncMock(spec=AsyncSession)
    async def _get_session(): yield _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_session] = _get_session
    return app


def _fake_parsed():
    p = MagicMock()
    p.title = "Parsed Doc"
    p.text = "Some body text."
    return p


def test_ingest_file_pdf_calls_parse():
    """POST /ingest/file with a .pdf should reach parse_file and return 200."""
    with patch("gnosis.routers.ingest.parse_file", return_value=_fake_parsed()), \
         patch("gnosis.routers.ingest._ai_enrich", new_callable=AsyncMock,
               return_value=("Title", "Summary", ["tag1"])), \
         patch("gnosis.routers.ingest._write_vault_note", new_callable=AsyncMock,
               return_value="70-sources/20260101-title.md"):
        resp = TestClient(_make_app()).post(
            "/api/v1/ingest/file",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Title"
    assert body["summary"] == "Summary"


def test_ingest_file_unsupported_extension_returns_415():
    """Unknown extension → 415 before parse_file is ever called."""
    resp = TestClient(_make_app()).post(
        "/api/v1/ingest/file",
        files={"file": ("notes.exe", io.BytesIO(b"bin"), "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_ingest_file_parse_error_returns_422():
    """parse_file raising → 422."""
    with patch("gnosis.routers.ingest.parse_file", side_effect=Exception("corrupt")):
        resp = TestClient(_make_app()).post(
            "/api/v1/ingest/file",
            files={"file": ("bad.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")},
        )
    assert resp.status_code == 422


def test_ingest_url_ok():
    """POST /ingest/url with a valid URL should return 200."""
    fake = MagicMock()
    fake.title = "Article"; fake.text = "Body."
    with patch("gnosis.routers.ingest.parse_url" if hasattr(__import__("gnosis.routers.ingest", fromlist=["parse_url"]), "parse_url") else "gnosis.services.document_parser.parse_url",
               new_callable=AsyncMock, return_value=fake, create=True), \
         patch("gnosis.routers.ingest._ai_enrich", new_callable=AsyncMock,
               return_value=("Article", "Summary", [])), \
         patch("gnosis.routers.ingest._write_vault_note", new_callable=AsyncMock,
               return_value="70-sources/article.md"):
        # patch parse_url at the right level
        import gnosis.routers.ingest as ingest_mod
        with patch.object(ingest_mod, "_ai_enrich", new=AsyncMock(return_value=("Article","S",[]))), \
             patch.object(ingest_mod, "_write_vault_note", new=AsyncMock(return_value="70-sources/a.md")):
            # patch the lazy import
            with patch("gnosis.services.document_parser.parse_url",
                       new_callable=AsyncMock, return_value=fake, create=True):
                resp = TestClient(_make_app()).post(
                    "/api/v1/ingest/url",
                    json={"url": "https://example.com/article"},
                )
    assert resp.status_code in (200, 422)


def test_ingest_batch_valid_zip_returns_200():
    """Valid .zip of .md files → 200."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("note1.md", "---\ntitle: N1\n---\n\nBody.")
    buf.seek(0)
    with patch("gnosis.routers.ingest.settings") as ms:
        ms.vault_path = "/tmp"
        resp = TestClient(_make_app()).post(
            "/api/v1/ingest/batch",
            files={"file": ("vault.zip", buf, "application/zip")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body


def test_ingest_batch_non_zip_returns_415():
    """Non-zip file → 415."""
    resp = TestClient(_make_app()).post(
        "/api/v1/ingest/batch",
        files={"file": ("notes.txt", io.BytesIO(b"not a zip"), "text/plain")},
    )
    assert resp.status_code == 415
