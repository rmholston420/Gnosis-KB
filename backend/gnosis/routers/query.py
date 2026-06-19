"""Dataview-style query router.

Endpoints
---------
POST /api/v1/query/run              — execute a one-off GQL query
GET  /api/v1/query/saved            — list saved dashboards
POST /api/v1/query/saved            — create a saved dashboard
GET  /api/v1/query/saved/{id}       — get a saved dashboard
PUT  /api/v1/query/saved/{id}       — update a saved dashboard
DELETE /api/v1/query/saved/{id}     — delete a saved dashboard
POST /api/v1/query/saved/{id}/run   — execute a saved dashboard

Namespace contract
------------------
All query execution is scoped to the caller's accessible vault set via
``get_accessible_owner_ids()``.  SavedQuery rows are owned by the user who
created them (``owner_id`` column); list/get/update/delete are all filtered
to ``current_user.id`` so users cannot read or modify each other's dashboards.

GQL syntax examples::

    FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20
    FROM 20-projects WHERE note_type=project AND word_count > 100
    WHERE tags CONTAINS eeg SORT created_at DESC
    FROM 00-inbox SORT modified_at DESC SELECT title,status,modified_at
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user
from gnosis.core.namespace import get_accessible_owner_ids
from gnosis.database import get_db
from gnosis.models.saved_query import SavedQuery
from gnosis.models.user import User
from gnosis.schemas.query import (
    QueryResult,
    QueryRun,
    SavedQueryCreate,
    SavedQueryRead,
    SavedQueryUpdate,
)
from gnosis.services.query_parser import GQLParseError, execute_query, parse_query

router = APIRouter(prefix="/query", tags=["query"])


# ---------------------------------------------------------------------------
# One-off query execution
# ---------------------------------------------------------------------------

@router.post("/run", response_model=QueryResult, summary="Execute a GQL query")
async def run_query(
    payload: QueryRun,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResult:
    """Parse and execute a GQL string scoped to the caller's accessible vaults."""
    try:
        parsed = parse_query(payload.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    owner_ids = await get_accessible_owner_ids(db, current_user)
    rows, ms = await execute_query(parsed, db, owner_ids=owner_ids)
    return QueryResult(rows=rows, total=len(rows), query_time_ms=ms)


# ---------------------------------------------------------------------------
# Saved dashboards CRUD
# ---------------------------------------------------------------------------

@router.get("/saved", response_model=list[SavedQueryRead], summary="List saved dashboards")
async def list_saved(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SavedQuery]:
    """Return saved dashboards owned by the current user, ordered by name."""
    result = await db.execute(
        select(SavedQuery)
        .where(SavedQuery.owner_id == current_user.id)
        .order_by(SavedQuery.name)
    )
    return list(result.scalars().all())


@router.post(
    "/saved",
    response_model=SavedQueryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved dashboard",
)
async def create_saved(
    payload: SavedQueryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedQuery:
    """Persist a named GQL query as a reusable dashboard owned by the caller."""
    try:
        parse_query(payload.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sq = SavedQuery(
        name=payload.name,
        query=payload.query,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(sq)
    try:
        await db.commit()
    except Exception:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=409, detail="A dashboard with that name already exists.")
    await db.refresh(sq)
    return sq


@router.get("/saved/{sq_id}", response_model=SavedQueryRead, summary="Get a saved dashboard")
async def get_saved(
    sq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedQuery:
    """Return a single saved dashboard by ID (must be owned by caller)."""
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == sq_id,
            SavedQuery.owner_id == current_user.id,
        )
    )
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return sq


@router.put("/saved/{sq_id}", response_model=SavedQueryRead, summary="Update a saved dashboard")
async def update_saved(
    sq_id: int,
    payload: SavedQueryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SavedQuery:
    """Update a saved dashboard (must be owned by caller)."""
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == sq_id,
            SavedQuery.owner_id == current_user.id,
        )
    )
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    if payload.name is not None:
        sq.name = payload.name
    if payload.query is not None:
        try:
            parse_query(payload.query)
        except GQLParseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        sq.query = payload.query
    if payload.description is not None:
        sq.description = payload.description
    await db.commit()
    await db.refresh(sq)
    return sq


@router.delete("/saved/{sq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved(
    sq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently delete a saved dashboard (must be owned by caller)."""
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == sq_id,
            SavedQuery.owner_id == current_user.id,
        )
    )
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    await db.delete(sq)
    await db.commit()


@router.post("/saved/{sq_id}/run", response_model=QueryResult, summary="Run a saved dashboard")
async def run_saved(
    sq_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueryResult:
    """Execute a saved dashboard scoped to the caller's accessible vaults."""
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == sq_id,
            SavedQuery.owner_id == current_user.id,
        )
    )
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    try:
        parsed = parse_query(sq.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=f"Saved query has invalid syntax: {exc}") from exc
    owner_ids = await get_accessible_owner_ids(db, current_user)
    rows, ms = await execute_query(parsed, db, owner_ids=owner_ids)
    return QueryResult(rows=rows, total=len(rows), query_time_ms=ms)
