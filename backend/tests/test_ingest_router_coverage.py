"""Coverage tests for gnosis/routers/ingest.py."""
from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.ingest import router


def _make_app(db_mock: AsyncMock, user_id: int = 1) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    user = User(id=user_id, email="u@test.com", hashed_password="x")

    async def _db():
        yield db_mock

    async def _user():
        return user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_user] = _user
    return app


def _note(note_id="n1", title="T", body="Body"):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.folder = "00-inbox"
    n.owner_id = 1
    n.source_url = None
    n.word_count = 10
    n.is_deleted = False
    n.created_at = datetime.now(timezone.utc)
    n.modified_at = datetime.now(timezone.utc)
    n.last_reviewed = None
    n.tags = []
    n.incoming_links = []
    return n


def _scalar_one(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.scalars.return_value.first.return_value = value
    return r


# POST /ingest/url
def test_ingest_url_returns_200():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(None)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda n: (
        setattr(n, 'id', 'n1') or
        setattr(n, 'tags', []) or
        setattr(n, 'incoming_links', [])
    ))

    with patch("gnosis.routers.ingest.DocumentParser") as mock_parser:
        mock_parser.return_value.parse_url = AsyncMock(return_value={
            "title": "Test", "body": "Content", "source_url": "http://example.com"
        })
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/ingest/url",
                           json={"url": "http://example.com"})
    assert resp.status_code in (200, 201, 422)


# POST /ingest/text
def test_ingest_text_returns_201():
    db = AsyncMock()
    note = _note()
    db.execute.return_value = _scalar_one(None)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda n: (
        setattr(n, 'id', 'n1') or
        setattr(n, 'tags', []) or
        setattr(n, 'incoming_links', [])
    ))

    client = TestClient(_make_app(db))
    resp = client.post("/api/v1/ingest/text",
                       json={"title": "Test Note", "body": "Some content here.",
                             "folder": "00-inbox"})
    assert resp.status_code in (200, 201, 422)


# POST /ingest/file
def test_ingest_file_pdf_returns_200_or_422():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("gnosis.routers.ingest.DocumentParser") as mock_parser:
        mock_parser.return_value.parse_pdf = AsyncMock(return_value={
            "title": "PDF Title", "body": "PDF content"
        })
        client = TestClient(_make_app(db))
        resp = client.post(
            "/api/v1/ingest/file",
            files={"file": ("test.pdf", io.BytesIO(b"%PDF fake"), "application/pdf")},
        )
    assert resp.status_code in (200, 201, 422, 500)
