"""Unit tests for gnosis/routers/query.py.

Covers: run_query (happy path, parse error), list_saved, create_saved
(happy + duplicate 409 + parse error 422), get_saved (found + 404),
update_saved (name/query/desc + 404 + bad query 422), delete_saved
(happy + 404), run_saved (happy + 404 + bad query 422).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(uid=1):
    u = MagicMock()
    u.id = uid
    return u


def _sq(sq_id=1, name="My Dashboard", query="FROM 10-zettelkasten", owner_id=1):
    sq = MagicMock()
    sq.id = sq_id
    sq.name = name
    sq.query = query
    sq.description = None
    sq.owner_id = owner_id
    return sq


def _db_returning(obj):
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    result.scalars.return_value.all.return_value = [obj] if obj else []
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# POST /query/run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_query_happy_path():
    from gnosis.routers.query import run_query
    from gnosis.schemas.query import QueryRun

    parsed = MagicMock()
    with (
        patch("gnosis.routers.query.parse_query", return_value=parsed),
        patch("gnosis.routers.query.execute_query", AsyncMock(return_value=([{"id": "1"}], 5.0))),
    ):
        result = await run_query(
            payload=QueryRun(query="FROM 10-zettelkasten"),
            db=AsyncMock(), owner_ids={1},
        )
    assert result.total == 1
    assert result.query_time_ms == 5.0


@pytest.mark.asyncio
async def test_run_query_returns_422_on_parse_error():
    from fastapi import HTTPException
    from gnosis.routers.query import run_query
    from gnosis.schemas.query import QueryRun
    from gnosis.services.query_parser import GQLParseError

    with (
        patch("gnosis.routers.query.parse_query", side_effect=GQLParseError("bad syntax")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await run_query(
            payload=QueryRun(query="INVALID !!"),
            db=AsyncMock(), owner_ids={1},
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# GET /query/saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_saved_returns_user_dashboards():
    from gnosis.routers.query import list_saved

    sq = _sq()
    db = _db_returning(sq)
    result = await list_saved(db=db, current_user=_user())
    assert len(result) == 1


# ---------------------------------------------------------------------------
# POST /query/saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_saved_happy_path():
    from gnosis.routers.query import create_saved
    from gnosis.schemas.query import SavedQueryCreate

    sq = _sq()
    db = _db_returning(sq)

    with patch("gnosis.routers.query.parse_query", return_value=MagicMock()):
        result = await create_saved(
            payload=SavedQueryCreate(name="My Dashboard", query="FROM 10-zettelkasten"),
            db=db, current_user=_user(),
        )
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_saved_returns_409_on_duplicate():
    from fastapi import HTTPException
    from gnosis.routers.query import create_saved
    from gnosis.schemas.query import SavedQueryCreate

    db = _db_returning(None)
    db.commit = AsyncMock(side_effect=Exception("unique constraint"))

    with (
        patch("gnosis.routers.query.parse_query", return_value=MagicMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await create_saved(
            payload=SavedQueryCreate(name="Dup", query="FROM 10-zettelkasten"),
            db=db, current_user=_user(),
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_saved_returns_422_on_bad_query():
    from fastapi import HTTPException
    from gnosis.routers.query import create_saved
    from gnosis.schemas.query import SavedQueryCreate
    from gnosis.services.query_parser import GQLParseError

    with (
        patch("gnosis.routers.query.parse_query", side_effect=GQLParseError("bad")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await create_saved(
            payload=SavedQueryCreate(name="Bad", query="INVALID"),
            db=AsyncMock(), current_user=_user(),
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# GET /query/saved/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_saved_returns_dashboard():
    from gnosis.routers.query import get_saved

    sq = _sq(sq_id=5)
    db = _db_returning(sq)
    result = await get_saved(sq_id=5, db=db, current_user=_user())
    assert result.id == 5


@pytest.mark.asyncio
async def test_get_saved_returns_404_when_missing():
    from fastapi import HTTPException
    from gnosis.routers.query import get_saved

    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc_info:
        await get_saved(sq_id=99, db=db, current_user=_user())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PUT /query/saved/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_saved_modifies_fields():
    from gnosis.routers.query import update_saved
    from gnosis.schemas.query import SavedQueryUpdate

    sq = _sq()
    db = _db_returning(sq)

    with patch("gnosis.routers.query.parse_query", return_value=MagicMock()):
        result = await update_saved(
            sq_id=1,
            payload=SavedQueryUpdate(name="New Name", query="FROM 20-projects", description="desc"),
            db=db, current_user=_user(),
        )
    assert sq.name == "New Name"
    assert sq.description == "desc"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_saved_returns_404_when_missing():
    from fastapi import HTTPException
    from gnosis.routers.query import update_saved
    from gnosis.schemas.query import SavedQueryUpdate

    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc_info:
        await update_saved(
            sq_id=99, payload=SavedQueryUpdate(),
            db=db, current_user=_user(),
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_saved_returns_422_on_bad_query():
    from fastapi import HTTPException
    from gnosis.routers.query import update_saved
    from gnosis.schemas.query import SavedQueryUpdate
    from gnosis.services.query_parser import GQLParseError

    sq = _sq()
    db = _db_returning(sq)
    with (
        patch("gnosis.routers.query.parse_query", side_effect=GQLParseError("bad")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_saved(
            sq_id=1,
            payload=SavedQueryUpdate(query="INVALID"),
            db=db, current_user=_user(),
        )
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /query/saved/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_saved_calls_db_delete():
    from gnosis.routers.query import delete_saved

    sq = _sq()
    db = _db_returning(sq)
    await delete_saved(sq_id=1, db=db, current_user=_user())
    db.delete.assert_awaited_once_with(sq)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_saved_returns_404_when_missing():
    from fastapi import HTTPException
    from gnosis.routers.query import delete_saved

    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc_info:
        await delete_saved(sq_id=99, db=db, current_user=_user())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# POST /query/saved/{id}/run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_saved_happy_path():
    from gnosis.routers.query import run_saved

    sq = _sq(query="FROM 10-zettelkasten")
    db = _db_returning(sq)
    parsed = MagicMock()
    with (
        patch("gnosis.routers.query.parse_query", return_value=parsed),
        patch("gnosis.routers.query.execute_query", AsyncMock(return_value=([{"id": "a"}], 3.0))),
    ):
        result = await run_saved(sq_id=1, db=db, current_user=_user(), owner_ids={1})
    assert result.total == 1


@pytest.mark.asyncio
async def test_run_saved_returns_404_when_missing():
    from fastapi import HTTPException
    from gnosis.routers.query import run_saved

    db = _db_returning(None)
    with pytest.raises(HTTPException) as exc_info:
        await run_saved(sq_id=99, db=db, current_user=_user(), owner_ids={1})
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_run_saved_returns_422_on_bad_saved_query():
    from fastapi import HTTPException
    from gnosis.routers.query import run_saved
    from gnosis.services.query_parser import GQLParseError

    sq = _sq(query="CORRUPT")
    db = _db_returning(sq)
    with (
        patch("gnosis.routers.query.parse_query", side_effect=GQLParseError("bad")),
        pytest.raises(HTTPException) as exc_info,
    ):
        await run_saved(sq_id=1, db=db, current_user=_user(), owner_ids={1})
    assert exc_info.value.status_code == 422
