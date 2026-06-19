"""Search router — hybrid BM25 + vector + PostgreSQL FTS fallback.

Mode routing
------------
hybrid   -- Qdrant BM25 + dense RRF fusion (default; falls back to FTS on
             Qdrant errors)
semantic -- Dense-only Qdrant vector search
fulltext -- PostgreSQL tsvector search (always works, even without Qdrant)

Namespace contract
------------------
Every search is scoped to the calling user's accessible vault set via the
``get_vault_owner_ids`` dependency, which honours the optional
``X-Vault-Owner-Id`` request header (sent by the frontend VaultSwitcher).

The ``owner_ids`` set is passed to ``hybrid_search()`` which injects a
Qdrant payload filter, and to ``fulltext_search()`` / ``suggest_completions()``
which use ``scoped_note_stmt`` under the hood.
"""

from typing import Optional
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gnosis.core.auth import get_current_user, get_vault_owner_ids
from gnosis.database import get_db
from gnosis.models.user import User
from gnosis.schemas.search import SearchResponse, SearchResult
from gnosis.services.fts import fulltext_search, suggest_completions
from gnosis.services.hybrid_search import hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/", response_model=SearchResponse, summary="Search notes")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=100),
    folder: Optional[str] = Query(None),
    note_type: Optional[str] = Query(None),
    tags: Optional[list[str]] = Query(None),
    mode: str = Query("hybrid", pattern="^(hybrid|semantic|fulltext)$"),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> SearchResponse:
    """Search the vault (scoped to the caller's accessible vaults).

    - **hybrid** (default): Qdrant BM25 + dense vector RRF fusion. Falls back
      to PostgreSQL FTS automatically if Qdrant is unavailable.
    - **semantic**: Dense-only vector search via Qdrant.
    - **fulltext**: PostgreSQL tsvector search. Always available; no Qdrant
      required. Best for exact phrase and keyword searches.
    """
    if mode == "fulltext":
        raw = await fulltext_search(
            db, q, owner_ids=owner_ids,
            limit=limit, folder=folder, note_type=note_type, tags=tags,
        )
        results = _map_results(raw["results"])
        return SearchResponse(
            query=q, mode=mode, results=results,
            total=len(results), elapsed_ms=raw["elapsed_ms"],
        )

    # hybrid / semantic — delegate to Qdrant service
    try:
        raw = hybrid_search(
            q, owner_ids=owner_ids,
            limit=limit, folder=folder, note_type=note_type, tags=tags,
        )
        results = _map_results(raw["results"])
        return SearchResponse(
            query=q, mode=mode, results=results,
            total=len(results), elapsed_ms=raw["elapsed_ms"],
        )
    except Exception as exc:
        # Qdrant unavailable — transparent fallback to FTS
        logger.warning(
            "Qdrant search failed (%s); falling back to PostgreSQL FTS", exc
        )
        raw = await fulltext_search(
            db, q, owner_ids=owner_ids,
            limit=limit, folder=folder, note_type=note_type, tags=tags,
        )
        results = _map_results(raw["results"])
        return SearchResponse(
            query=q,
            mode="fulltext",  # report actual mode used
            results=results,
            total=len(results),
            elapsed_ms=raw["elapsed_ms"],
        )


@router.get("/suggest", response_model=list[str], summary="Title autocomplete")
async def suggest(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    owner_ids: set[int] = Depends(get_vault_owner_ids),
) -> list[str]:
    """Return note titles that start with *q* for search-bar autocomplete.

    Scoped to the caller's accessible vaults.
    """
    return await suggest_completions(db, q, owner_ids=owner_ids, limit=limit)


def _map_results(raw_results: list[dict]) -> list[SearchResult]:
    return [
        SearchResult(
            note_id=r["note_id"],
            title=r["title"],
            slug=r.get("slug", ""),
            folder=r["folder"],
            note_type=r["note_type"],
            status=r["status"],
            score=r["score"],
            highlight=r["highlight"],
            tags=r["tags"],
        )
        for r in raw_results
    ]
