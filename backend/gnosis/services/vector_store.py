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
"""

import logging
from typing import Any, Optional

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from gnosis.config import get_settings
from gnosis.services.embeddings import embed_dense, embed_colbert

logger = logging.getLogger(__name__)

# Sentinel stored in Qdrant for notes whose owner is unknown (legacy / null)
_LEGACY_OWNER_SENTINEL = 0

_client: Optional[QdrantClient] = None


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
    """Upsert a note into the Qdrant collection.

    Generates dense and ColBERT embeddings. Sparse (BM25) embeddings
    are computed by Qdrant server-side via the fastembed-server integration.

    The ``owner_id`` is stored in the payload as an integer.  Callers
    should always pass the note's ``owner_id``; ``None`` is stored as the
    legacy sentinel (``0``) and will be visible to all users until a
    backfill re-indexes the note with the correct owner.

    Args:
        note_id: Note primary key.
        title: Note title (included in text for embedding).
        body: Note body Markdown text.
        folder: PARA folder name.
        note_type: Note type string.
        status: Note status string.
        tags: List of tag names.
        owner_id: User ID that owns this note, or None for legacy notes.
    """
    client = get_qdrant_client()
    settings = get_settings()

    text = f"{title}\n\n{body}"

    try:
        dense_vec = embed_dense(text)
        colbert_vec = embed_colbert(text)
    except Exception as e:
        logger.warning("Embedding failed for note %s: %s", note_id, e)
        return

    point = models.PointStruct(
        id=note_id,
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
            # Store sentinel 0 for legacy/unowned notes so the field is
            # always present and filterable.
            "owner_id": owner_id if owner_id is not None else _LEGACY_OWNER_SENTINEL,
        },
    )

    client.upsert(
        collection_name=settings.qdrant_collection_name,
        points=[point],
    )
    logger.debug("Upserted note %s (owner=%s) into Qdrant", note_id, owner_id)


def delete_note(note_id: str) -> None:
    """Remove a note from the Qdrant collection.

    Args:
        note_id: Note primary key.
    """
    client = get_qdrant_client()
    settings = get_settings()
    client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=models.PointIdsList(points=[note_id]),
    )
    logger.debug("Deleted note %s from Qdrant", note_id)
