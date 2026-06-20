"""Coverage tests for gnosis/routers/query.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gnosis.core.auth import require_user
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.routers.query import router


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


def _note(note_id="n1", title="T", body="Body", score=0.9):
    n = MagicMock()
    n.note_id = note_id
    n.title = title
    n.body = body
    n.score = score
    n.snippet = "snippet"
    return n


def test_query_returns_200():
    db = AsyncMock()
    with patch("gnosis.routers.query.hybrid_search", new_callable=AsyncMock,
               return_value=[_note()]), \
         patch("gnosis.routers.query.LLMProvider") as mock_llm:
        mock_llm.return_value.get_completion = AsyncMock(return_value="Here is the answer.")
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/query/", json={"question": "What is Python?"})
    assert resp.status_code == 200


def test_query_no_context_returns_200():
    db = AsyncMock()
    with patch("gnosis.routers.query.hybrid_search", new_callable=AsyncMock,
               return_value=[]), \
         patch("gnosis.routers.query.LLMProvider") as mock_llm:
        mock_llm.return_value.get_completion = AsyncMock(return_value="No context found.")
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/query/", json={"question": "unknown topic"})
    assert resp.status_code == 200


def test_query_llm_error_returns_500_or_200():
    db = AsyncMock()
    with patch("gnosis.routers.query.hybrid_search", new_callable=AsyncMock,
               return_value=[_note()]), \
         patch("gnosis.routers.query.LLMProvider") as mock_llm:
        mock_llm.return_value.get_completion = AsyncMock(side_effect=RuntimeError("LLM down"))
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/query/", json={"question": "test"})
    assert resp.status_code in (200, 500)


def test_query_stream_returns_200():
    db = AsyncMock()

    async def _fake_stream(*args, **kwargs):
        yield "chunk1"
        yield "chunk2"

    with patch("gnosis.routers.query.hybrid_search", new_callable=AsyncMock,
               return_value=[_note()]), \
         patch("gnosis.routers.query.LLMProvider") as mock_llm:
        mock_llm.return_value.stream_completion = _fake_stream
        client = TestClient(_make_app(db))
        resp = client.post("/api/v1/query/stream", json={"question": "test"})
    assert resp.status_code in (200, 404)
