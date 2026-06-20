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

    The point ID is a UUID v5 derived from ``note_id`` (Qdrant requires
    UUID or unsigned int).  The original ``note_id`` string is preserved
    in the payload for DB join-back.

    Args:
        note_id: Note primary key (arbitrary string).
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
    """Remove a note from the Qdrant collection.

    Args:
        note_id: Note primary key (arbitrary string).
    """
    client = get_qdrant_client()
    settings = get_settings()
    point_uuid = _note_id_to_uuid(note_id)
    client.delete(
        collection_name=settings.qdrant_collection_name,
        points_selector=models.PointIdsList(points=[point_uuid]),
    )
    logger.debug("Deleted note %s (uuid=%s) from Qdrant", note_id, point_uuid)
