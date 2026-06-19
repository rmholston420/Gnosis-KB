"""Search router — hybrid BM25 + vector search."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.database import get_db
from gnosis.schemas.search import SearchResponse, SearchResult
from gnosis.services.hybrid_search import hybrid_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/", response_model=SearchResponse, summary="Hybrid search (BM25 + vector)")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    folder: Optional[str] = Query(None),
    note_type: Optional[str] = Query(None),
    tags: Optional[list[str]] = Query(None),
    mode: str = Query("hybrid", regex="^(hybrid|semantic|fulltext)$"),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Run hybrid search over the vault using BM25 + dense vector RRF fusion.

    Args:
        q: Search query string.
        limit: Maximum results to return.
        folder: Optional PARA folder filter.
        note_type: Optional note type filter.
        tags: Optional tag filters.
        mode: Search mode (hybrid/semantic/fulltext).
        db: Database session.

    Returns:
        SearchResponse with results, scores, and highlights.
    """
    raw = hybrid_search(q, limit=limit, folder=folder, note_type=note_type, tags=tags)
    results = [
        SearchResult(
            note_id=r["note_id"],
            title=r["title"],
            slug="",
            folder=r["folder"],
            note_type=r["note_type"],
            status=r["status"],
            score=r["score"],
            highlight=r["highlight"],
            tags=r["tags"],
        )
        for r in raw["results"]
    ]
    return SearchResponse(
        query=q,
        mode=mode,
        results=results,
        total=len(results),
        elapsed_ms=raw["elapsed_ms"],
    )
