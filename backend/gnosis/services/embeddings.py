"""Embedding service — generate dense vectors via Ollama or OpenAI.

Public API
----------
embed_text(text: str) -> list[float] | None
    Embed a single string. Returns None on failure (caller decides fallback).

embed_batch(texts: list[str]) -> list[list[float]]
    Embed a list of strings. Returns empty list on total failure.
    Partial failures return a list of the successfully-embedded vectors.

embed_dense(text: str) -> list[float]
    Alias used by vector_store.py and hybrid_search.py. Raises RuntimeError
    on failure so callers can distinguish "no results" from "embedding error".

embed_colbert(text: str) -> list[list[float]]
    Generate a ColBERT multi-vector representation (list of per-token vectors).
    Falls back to wrapping the dense vector in a list when a dedicated ColBERT
    model is unavailable, which is sufficient for the MAX_SIM comparator.

Fix (2025-06-26)
----------------
- embed_dense and embed_colbert were missing entirely, causing an ImportError
  that crashed vector_store.py and hybrid_search.py at import time, making
  every vector upsert and every search call fail with a 500.
- Both functions previously swallowed ALL exceptions and returned None / []
  with no log emission at ERROR level. Fixed: log at ERROR with exc_info.
"""

from __future__ import annotations

import logging
from typing import Any

from gnosis.config import get_settings

logger = logging.getLogger(__name__)


def _get_ollama_client() -> Any:
    """Return a lazy-imported OllamaClient instance."""
    from ollama import Client  # type: ignore[import]

    settings = get_settings()
    return Client(host=settings.ollama_base_url)


def embed_text(text: str) -> list[float] | None:
    """Generate a dense embedding for *text*.

    Returns the embedding vector on success, or ``None`` on failure.
    Callers must handle ``None`` gracefully (e.g. skip vector upsert).

    Args:
        text: The text to embed. Will be truncated to 8192 chars if longer.

    Returns:
        A list of floats (the embedding vector), or None on error.
    """
    settings = get_settings()
    text = text[:8192]  # guard against oversized inputs

    try:
        if settings.openai_api_key:
            import openai  # type: ignore[import]

            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding

        client = _get_ollama_client()
        response = client.embeddings(
            model=settings.ollama_embed_model,
            prompt=text,
        )
        return response["embedding"]

    except Exception as exc:
        # Fix: was silently returning None. Now logs at ERROR so operators
        # can detect misconfigured models or Ollama connectivity issues.
        logger.error(
            "embed_text failed (model=%s): %s",
            settings.ollama_embed_model,
            exc,
            exc_info=True,
        )
        return None


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Generate dense embeddings for a batch of texts.

    Attempts to embed all texts. On total failure returns an empty list.
    On partial failure, successfully-embedded vectors are returned and
    failures are logged individually at WARNING level.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors. May be shorter than *texts* on partial failure.
    """
    if not texts:
        return []

    settings = get_settings()

    try:
        if settings.openai_api_key:
            import openai  # type: ignore[import]

            client = openai.OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[t[:8192] for t in texts],
            )
            return [item.embedding for item in response.data]

        # Ollama: embed one at a time (no native batch endpoint)
        client = _get_ollama_client()
        results: list[list[float]] = []
        for i, text in enumerate(texts):
            try:
                response = client.embeddings(
                    model=settings.ollama_embed_model,
                    prompt=text[:8192],
                )
                results.append(response["embedding"])
            except Exception as item_exc:  # noqa: BLE001
                logger.warning(
                    "embed_batch: failed to embed item %d/%d: %s",
                    i + 1,
                    len(texts),
                    item_exc,
                )
        return results

    except Exception as exc:
        # Fix: was silently returning []. Now logs at ERROR.
        logger.error(
            "embed_batch failed entirely (model=%s, n=%d): %s",
            settings.ollama_embed_model,
            len(texts),
            exc,
            exc_info=True,
        )
        return []


def embed_dense(text: str) -> list[float]:
    """Generate a dense embedding vector, raising on failure.

    This is the primary embedding entry-point used by vector_store.py and
    hybrid_search.py. Unlike embed_text() it raises RuntimeError on failure
    so callers can distinguish a genuine empty result set from an embedding
    infrastructure problem.

    Fix (2025-06-26): this function was missing entirely, causing an ImportError
    that crashed every vector upsert and every search request at import time.

    Args:
        text: The text to embed.

    Returns:
        A non-empty list of floats representing the embedding vector.

    Raises:
        RuntimeError: If the embedding call fails for any reason.
    """
    vec = embed_text(text)
    if vec is None:
        raise RuntimeError(
            f"embed_dense: embedding returned None for text starting with {text[:80]!r}"
        )
    return vec


def embed_colbert(text: str) -> list[list[float]]:
    """Generate a ColBERT multi-vector (list of per-token vectors).

    ColBERT MAX_SIM scoring requires a list of vectors, one per token.
    When a dedicated ColBERT model is unavailable (the common case with
    Ollama), we fall back to wrapping the single dense vector in a list.
    This degrades ColBERT reranking to standard cosine similarity but
    avoids a hard dependency on a separate ColBERT endpoint.

    Fix (2025-06-26): this function was missing entirely, causing an ImportError
    that crashed vector_store.py at import time and silently dropped all
    vector upserts on every note save.

    Args:
        text: The text to embed.

    Returns:
        A list of embedding vectors (multivector). At minimum a single-element
        list containing the dense vector.

    Raises:
        RuntimeError: If the underlying embedding call fails.
    """
    # Future: call a dedicated ColBERT endpoint here when available.
    # For now, wrap the dense vector to satisfy the multivector schema.
    dense = embed_dense(text)
    return [dense]
