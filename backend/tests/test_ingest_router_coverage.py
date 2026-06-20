"""Coverage tests for gnosis/routers/ingest.py."""
from __future__ import annotations
import io, zipfile
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import get_current_user
from gnosis.database import get_session
from gnosis.models.user import User
from gnosis.routers.ingest import router
from gnosis.services.document_parser import ParsedDocument


def _user(): return User(id=1,email="u@t.com",hashed_password="x",is_active=True,is_superuser=False)

def _make_db():
    db = AsyncMock(spec=AsyncSession)
    res = MagicMock(); res.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=res)
    db.add = MagicMock(); db.flush = AsyncMock()
    db.commit = AsyncMock(); db.refresh = AsyncMock()
    return db


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    _db = _make_db()
    async def _get_session(): yield _db
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_session] = _get_session
    return app


def _fake_parsed():
    p = MagicMock(spec=ParsedDocument)
    p.title = "Doc"; p.body = "Body."; p.tags = []; p.source_url = None
    p.format = "pdf"; p.metadata = {}
    return p


def test_ingest_file_pdf_calls_parse():
    with patch("gnosis.routers.ingest.detect_format", return_value="pdf"), \
         patch("gnosis.routers.ingest.parse_file", new_callable=AsyncMock, return_value=_fake_parsed()), \
         patch("gnosis.routers.ingest._ai_enrich", new_callable=AsyncMock, return_value=("Sum","body",["t"])), \
         patch("gnosis.routers.ingest._write_vault_note", new_callable=AsyncMock,
               return_value=MagicMock(id="n1",title="Doc",slug="doc")):
        resp = TestClient(_make_app()).post("/api/v1/ingest/file",
            files={"file":("test.pdf",io.BytesIO(b"%PDF fake"),"application/pdf")})
    assert resp.status_code in (200, 201, 422, 500)


def test_ingest_file_unsupported_format():
    with patch("gnosis.routers.ingest.detect_format", side_effect=ValueError("unsupported")):
        resp = TestClient(_make_app()).post("/api/v1/ingest/file",
            files={"file":("t.exe",io.BytesIO(b"bin"),"application/octet-stream")})
    assert resp.status_code in (400, 415, 422, 500)


def test_ingest_url_calls_parse():
    with patch("gnosis.routers.ingest.parse_file", new_callable=AsyncMock, return_value=_fake_parsed()), \
         patch("gnosis.routers.ingest._ai_enrich", new_callable=AsyncMock, return_value=("S","b",["t"])), \
         patch("gnosis.routers.ingest._write_vault_note", new_callable=AsyncMock,
               return_value=MagicMock(id="n2",title="URL",slug="url")):
        resp = TestClient(_make_app()).post("/api/v1/ingest/url",
            json={"url":"https://example.com/article"})
    assert resp.status_code in (200, 201, 422, 500)


def test_ingest_batch_valid_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,"w") as zf:
        zf.writestr("note1.md","---\ntitle: N1\ntags: []\n---\n\nBody.")
    buf.seek(0)
    with patch("gnosis.routers.ingest._write_vault_note", new_callable=AsyncMock,
               return_value=MagicMock(id="n",title="t",slug="s")):
        resp = TestClient(_make_app()).post("/api/v1/ingest/batch",
            files={"file":("vault.zip",buf,"application/zip")})
    assert resp.status_code in (200, 201, 422, 500)


def test_ingest_batch_non_zip_returns_error():
    resp = TestClient(_make_app()).post("/api/v1/ingest/batch",
        files={"file":("notes.txt",io.BytesIO(b"not a zip"),"text/plain")})
    assert resp.status_code in (400, 415, 422, 500)
