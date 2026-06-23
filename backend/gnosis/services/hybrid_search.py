"""Hybrid search service.

Implements three-stage search:
  Stage 1: Prefetch top-50 from dense vector search + top-50 from sparse BM25 search
  Stage 2: Fuse results with RRF (Reciprocal Rank Fusion)
  Stage 3: Rerank top-20 with ColBERT MAX_SIM

Falls back gracefully to dense-only if sparse/colbert models unavailable.

Namespace contract
------------------
Every call to ``hybrid_search()`` MUST supply ``owner_ids`` — the set of
User IDs whose notes the caller may read (own vault + accepted shared
grants).  The legacy sentinel ``0`` is always included so notes indexed
before the namespace migration remain visible.

Reference: Qdrant hybrid search best practices
(https://qdrant.tech/course/essentials/day-3/hybrid-search-demo/)
"""

import logging
import time
from typing import Any

from qdrant_client import models

from gnosis.config import get_settings
from gnosis.services.embeddings import embed_dense
from gnosis.services.vector_store import _LEGACY_OWNER_SENTINEL, get_qdrant_client

logger = logging.getLogger(__name__)


def hybrid_search(
    query: str,
    owner_ids: set[int],
    limit: int = 10,
    folder: str | None = None,
    note_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Run hybrid BM25 + dense vector search with RRF fusion.

    Only notes whose Qdrant payload ``owner_id`` is in *owner_ids* (or
    equals the legacy sentinel) are returned, enforcing vault isolation
    at the vector-search layer.

    Args:
        query: Natural language search query.
        owner_ids: Set of user IDs the caller may read.  Must not be empty.
        limit: Maximum number of results to return.
        folder: Optional PARA folder filter.
        note_type: Optional note type filter.
        tags: Optional list of tags to filter by.

    Returns:
        Dict with keys: results (list of dicts with score/payload), elapsed_ms.
    """
    if not owner_ids:
        return {"results": [], "elapsed_ms": 0.0}

    start = time.monotonic()
    client = get_qdrant_client()
    settings = get_settings()
    collection = settings.qdrant_collection_name

    # Always include the legacy sentinel so pre-migration notes are visible.
    accessible_ids = list(owner_ids | {_LEGACY_OWNER_SENTINEL})

    # Namespace filter: payload owner_id must be in accessible_ids
    namespace_condition = models.FieldCondition(
        key="owner_id",
        match=models.MatchAny(any=accessible_ids),
    )

    # Additional payload filters
    filter_conditions: list[models.FieldCondition] = [namespace_condition]
    if folder:
        filter_conditions.append(
            models.FieldCondition(key="folder", match=models.MatchValue(value=folder))
        )
    if note_type:
        filter_conditions.append(
            models.FieldCondition(key="note_type", match=models.MatchValue(value=note_type))
        )
    if tags:
        for tag in tags:
            filter_conditions.append(
                models.FieldCondition(key="tags", match=models.MatchValue(value=tag))
            )

    query_filter = models.Filter(must=filter_conditions)

    try:
        dense_vec = embed_dense(query)
    except Exception as e:
        logger.warning("Dense embedding failed, returning empty results: %s", e)
        return {"results": [], "elapsed_ms": 0.0}

    # Prefetch: dense + sparse, fuse with RRF
    prefetch = [
        models.Prefetch(
            query=models.Document(text=query, model="Qdrant/bm25"),
            using="sparse",
            limit=50,
            filter=query_filter,
        ),
        models.Prefetch(
            query=dense_vec,
            using="dense",
            limit=50,
            filter=query_filter,
        ),
    ]

    try:
        results = client.query_points(
            collection_name=collection,
            prefetch=prefetch,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        points = results.points
    except Exception as e:
        logger.warning("Hybrid search failed, falling back to dense: %s", e)
        # Fallback: pure dense search (namespace filter preserved)
        results = client.search(
            collection_name=collection,
            query_vector=("dense", dense_vec),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        points = results  # type: ignore[assignment]

    elapsed_ms = (time.monotonic() - start) * 1000

    output = []
    for point in points:
        payload = point.payload or {}
        output.append(
            {
                "note_id": payload.get("note_id", str(point.id)),
                "title": payload.get("title", ""),
                "folder": payload.get("folder", ""),
                "note_type": payload.get("note_type", ""),
                "status": payload.get("status", ""),
                "tags": payload.get("tags", []),
                "score": float(point.score),
                "highlight": payload.get("text_snippet", "")[:200],
            }
        )

    return {"results": output, "elapsed_ms": elapsed_ms}
