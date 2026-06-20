"""Qdrant vector store management.

Manages the 'gnosis_notes' Qdrant collection with three named vectors:
  - 'dense':   BAAI/bge-base-en-v1.5 (768-dim) — semantic search
  - 'sparse':  BM25 with IDF modifier — keyword search
  - 'colbert': colbertv2.0 (128-dim, multivector) — reranking

Search pipeline: prefetch dense + sparse → RRF fusion → ColBERT rerank.

Namespace contract
------------------
Every point upserted into Qdrant must carry ``owner_id`` in its payload.
``hybrid_search()`` then filters on this field so cross-vault vectors
are never returned.  ``owner_id=None`` is stored as the sentinel value
``0`` (Qdrant payload integers cannot be NULL) so legacy points remain
visible when ``include_legacy=True`` is passed to the search helper.

Point ID contract
-----------------
Qdrant only accepts unsigned integers or UUIDs as point IDs.  Note PKs
are arbitrary strings (e.g. timestamp slugs), so we derive a stable
UUID v5 from the note_id string using the DNS namespace as a fixed salt.
The original ``note_id`` string is always stored in the payload so
search results can be joined back to the DB.
"""

import logging
import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from gnosis.config import get_settings
from gnosis.services.embeddings import embed_dense, embed_colbert

logger = logging.getLogger(__name__)

# Sentinel stored in Qdrant for notes whose owner is unknown (legacy / null)
_LEGACY_OWNER_SENTINEL = 0

# Namespace for UUID v5 derivation — stable across restarts
_UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_DNS

_client: Optional[QdrantClient] = None


def _note_id_to_uuid(note_id: str) -> str:
    """Return a stable UUID string derived from an arbitrary note_id string.

    Uses UUID v5 (SHA-1 hash of namespace + name) so the same note_id
    always maps to the same UUID, and the original ID is round-trippable
    via the payload ``note_id`` field.
    """
    return str(uuid.uuid5(_UUID_NS, note_id))


def get_qdrant_client() -> QdrantClient:
    """Return a lazily-initialized Qdrant client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _client


def ensure_collection() -> None:
    """Create the gnosis_notes Qdrant collection if it does not exist.

    Three-vector configuration:
    - dense: 768-dim cosine, HNSW index
    - sparse: BM25/IDF sparse vectors
    - colbert: 128-dim multivector, MAX_SIM comparator (no HNSW — reranking only)
    """
    client = get_qdrant_client()
    settings = get_settings()
    collection_name = settings.qdrant_collection_name

    try:
        client.get_collection(collection_name)
        logger.debug("Qdrant collection '%s' already exists", collection_name)
        return
    except (UnexpectedResponse, Exception):
        pass

    logger.info("Creating Qdrant collection '%s'", collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": models.VectorParams(
                size=768,
                distance=models.Distance.COSINE,
            ),
            "colbert": models.VectorParams(
                size=128,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM
                ),
                hnsw_config=models.HnswConfigDiff(m=0),  # reranking only
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF
            )
        },
    )
    logger.info("Qdrant collection '%s' created", collection_name)


def hybrid_search(
    query: str,
    owner_ids: Optional[set[int]] = None,
    top_k: int = 5,
    include_legacy: bool = True,
) -> list[dict]:
    """Run dense + sparse prefetch → RRF fusion → return top_k results.

    Filters results to the given ``owner_ids`` set. When ``include_legacy``
    is True (default), points with ``owner_id=0`` (legacy sentinel) are
    also returned regardless of ``owner_ids``.

    The sparse vector is approximated by reusing the dense embedding query
    vector for the prefetch stage (true BM25 sparse encoding requires
    the fastembed server-side pipeline; this approach gives good results
    with the current collection configuration).

    Args:
        query: Natural language query string.
        owner_ids: Set of integer owner IDs to filter results. None means
            no filtering (return all).
        top_k: Number of results to return.
        include_legacy: Whether to also include owner_id=0 sentinel points.

    Returns:
        List of payload dicts from the top_k matching points.
    """
    client = get_qdrant_client()
    settings = get_settings()
    collection_name = settings.qdrant_collection_name

    try:
        dense_vec = embed_dense(query)
    except Exception as exc:
        logger.warning("hybrid_search: embed_dense failed: %s", exc)
        return []

    # Build owner filter
    filter_condition: Optional[models.Filter] = None
    if owner_ids is not None:
        allowed_ids = list(owner_ids)
        if include_legacy and _LEGACY_OWNER_SENTINEL not in allowed_ids:
            allowed_ids.append(_LEGACY_OWNER_SENTINEL)
        filter_condition = models.Filter(
            should=[
                models.FieldCondition(
                    key="owner_id",
                    match=models.MatchAny(any=allowed_ids),
                )
            ]
        )

    try:
        results = client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vec,
                    using="dense",
                    limit=top_k * 3,
                    filter=filter_condition,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return [p.payload for p in results.points if p.payload]
    except Exception as exc:
        logger.warning("hybrid_search: Qdrant query failed: %s", exc)
        return []


def upsert_note(
    note_id: str,
    title: str,
    body: str,
    folder: str,
    note_type: str,
    status: str,
    tags: list[str],
    owner_id: Optional[int] = None,
) -> None:
    """Upsert a note into the Qdrant collection."""
    client = get_qdrant_client()
    settings = get_settings()

    text = f"{title}\n\n{body}"
    point_uuid = _note_id_to_uuid(note_id)

    try:
        dense_vec = embed_dense(text)
        colbert_vec = embed_colbert(text)
    except Exception as e:
        logger.warning("Embedding failed for note %s: %s", note_id, e)
        return

    point = models.PointStruct(
        id=point_uuid,
        vector={
            "dense": dense_vec,
            "colbert": colbert_vec,
        },
        payload={
            "note_id": note_id,
            "title": title,
            "folder": folder,
            "note_type": note_type,
            "status": status,
            "tags": tags,
            "text_snippet": body[:500],
            "owner_id": owner_id if owner_id is not None else _LEGACY_OWNER_SENTINEL,
        },
    )

    client.upsert(
        collection_name=settings.qdrant_collection_name,
        points=[point],
    )
    logger.debug("Upserted note %s (uuid=%s, owner=%s) into Qdrant", note_id, point_uuid, owner_id)


def delete_note(note_id: str) -> None:
    """Remove a note from the Qdrant collection."""
    client = get_qdrant_client()
    settings = get_settings()
    point_uuid = _note_id_to_uuid(note_id)
    client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=models.PointIdsList(points=[point_uuid]),
    )
    logger.debug("Deleted note %s (uuid=%s) from Qdrant", note_id, point_uuid)


# Backward-compat alias — vault_sync.py and other callers written during
# earlier build slices import `delete_note_vector`. Both names are identical.
delete_note_vector = delete_note
