"""Coverage tests for gnosis/routers/search.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.routers.search import router


def _fake_fts():
    return {"results": [{"note_id":"abc","title":"T","slug":"t","folder":"00-inbox",
        "note_type":"note","status":"active","score":0.9,"highlight":"<mark>t</mark>","tags":[]}],
        "elapsed_ms":1.0}


def _make_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: None
    app.dependency_overrides[get_vault_owner_ids] = lambda: {1}
    return app


def test_search_fulltext_mode_returns_200():
    with patch("gnosis.routers.search.fulltext_search", new_callable=AsyncMock, return_value=_fake_fts()):
        resp = TestClient(_make_app()).get("/api/v1/search/?q=test&mode=fulltext")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "fulltext"


def test_search_hybrid_mode_returns_200():
    with patch("gnosis.routers.search.hybrid_search", return_value=_fake_fts()):
        resp = TestClient(_make_app()).get("/api/v1/search/?q=test&mode=hybrid")
    assert resp.status_code == 200


def test_search_hybrid_falls_back_to_fulltext():
    with patch("gnosis.routers.search.hybrid_search", side_effect=RuntimeError("qdrant down")), \
         patch("gnosis.routers.search.fulltext_search", new_callable=AsyncMock, return_value=_fake_fts()):
        resp = TestClient(_make_app()).get("/api/v1/search/?q=test&mode=hybrid")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "fulltext"


def test_search_semantic_mode_returns_200():
    with patch("gnosis.routers.search.hybrid_search", return_value=_fake_fts()):
        resp = TestClient(_make_app()).get("/api/v1/search/?q=test&mode=semantic")
    assert resp.status_code == 200


def test_search_missing_q_returns_422():
    resp = TestClient(_make_app()).get("/api/v1/search/")
    assert resp.status_code == 422


def test_suggest_returns_list():
    with patch("gnosis.routers.search.suggest_completions", new_callable=AsyncMock, return_value=["A","B"]):
        resp = TestClient(_make_app()).get("/api/v1/search/suggest?q=a")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_suggest_empty():
    with patch("gnosis.routers.search.suggest_completions", new_callable=AsyncMock, return_value=[]):
        resp = TestClient(_make_app()).get("/api/v1/search/suggest?q=xyz")
    assert resp.json() == []
