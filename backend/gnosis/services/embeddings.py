"""Embedding generation service using fastembed.

Provides dense (BAAI/bge-base-en-v1.5) and ColBERT (colbertv2.0) embeddings
for Qdrant hybrid search. fastembed runs fully locally — no GPU required.
"""

import logging

logger = logging.getLogger(__name__)

# Lazy-loaded models (initialized on first use to avoid slow startup)
_dense_model: object | None = None
_colbert_model: object | None = None


def get_dense_model() -> object:
    """Return the lazy-loaded dense embedding model.

    Uses BAAI/bge-base-en-v1.5 (768-dim) via fastembed.
    """
    global _dense_model
    if _dense_model is None:
        try:
            from fastembed import TextEmbedding  # type: ignore[import-untyped]
            _dense_model = TextEmbedding(model_name="BAAI/bge-base-en-v1.5")
            logger.info("Dense embedding model loaded: BAAI/bge-base-en-v1.5")
        except Exception as e:
            logger.warning("Could not load dense embedding model: %s", e)
            raise
    return _dense_model


def get_colbert_model() -> object:
    """Return the lazy-loaded ColBERT multivector model.

    Uses colbertv2.0 (128-dim) via fastembed for reranking.
    """
    global _colbert_model
    if _colbert_model is None:
        try:
            from fastembed import LateInteractionTextEmbedding  # type: ignore[import-untyped]
            _colbert_model = LateInteractionTextEmbedding(model_name="colbert-ir/colbertv2.0")
            logger.info("ColBERT model loaded: colbertv2.0")
        except Exception as e:
            logger.warning("Could not load ColBERT model: %s", e)
            raise
    return _colbert_model


def embed_dense(text: str) -> list[float]:
    """Generate a dense embedding vector for the given text.

    Args:
        text: Input text to embed.

    Returns:
        768-dimensional float list.
    """
    model = get_dense_model()
    embeddings = list(model.embed([text]))  # type: ignore[union-attr]
    return [float(x) for x in embeddings[0]]


def embed_colbert(text: str) -> list[list[float]]:
    """Generate ColBERT multivector embeddings for the given text.

    Args:
        text: Input text to embed.

    Returns:
        List of 128-dimensional float lists (one per token).
    """
    model = get_colbert_model()
    embeddings = list(model.embed([text]))  # type: ignore[union-attr]
    return [[float(x) for x in vec] for vec in embeddings[0]]
