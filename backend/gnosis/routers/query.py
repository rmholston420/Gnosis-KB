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

from gnosis.database import get_db
from gnosis.models.saved_query import SavedQuery
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
) -> QueryResult:
    """Parse and execute a Gnosis Query Language string against the vault.

    Returns a list of matching note rows with the requested columns.
    """
    try:
        parsed = parse_query(payload.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows, ms = await execute_query(parsed, db)
    return QueryResult(rows=rows, total=len(rows), query_time_ms=ms)


# ---------------------------------------------------------------------------
# Saved dashboards CRUD
# ---------------------------------------------------------------------------

@router.get("/saved", response_model=list[SavedQueryRead], summary="List saved dashboards")
async def list_saved(
    db: AsyncSession = Depends(get_db),
) -> list[SavedQuery]:
    """Return all saved Dataview dashboards, ordered by name."""
    result = await db.execute(select(SavedQuery).order_by(SavedQuery.name))
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
) -> SavedQuery:
    """Persist a named GQL query as a reusable dashboard."""
    # Validate GQL before saving
    try:
        parse_query(payload.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sq = SavedQuery(name=payload.name, query=payload.query, description=payload.description)
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
) -> SavedQuery:
    """Return a single saved dashboard by ID."""
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == sq_id))
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return sq


@router.put("/saved/{sq_id}", response_model=SavedQueryRead, summary="Update a saved dashboard")
async def update_saved(
    sq_id: int,
    payload: SavedQueryUpdate,
    db: AsyncSession = Depends(get_db),
) -> SavedQuery:
    """Update the name, query, or description of a saved dashboard."""
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == sq_id))
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


@router.delete("/saved/{sq_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a saved dashboard")
async def delete_saved(
    sq_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Permanently delete a saved dashboard."""
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == sq_id))
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    await db.delete(sq)
    await db.commit()


@router.post("/saved/{sq_id}/run", response_model=QueryResult, summary="Run a saved dashboard")
async def run_saved(
    sq_id: int,
    db: AsyncSession = Depends(get_db),
) -> QueryResult:
    """Execute a saved dashboard and return fresh results."""
    result = await db.execute(select(SavedQuery).where(SavedQuery.id == sq_id))
    sq = result.scalar_one_or_none()
    if sq is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    try:
        parsed = parse_query(sq.query)
    except GQLParseError as exc:
        raise HTTPException(status_code=422, detail=f"Saved query has invalid syntax: {exc}") from exc
    rows, ms = await execute_query(parsed, db)
    return QueryResult(rows=rows, total=len(rows), query_time_ms=ms)
