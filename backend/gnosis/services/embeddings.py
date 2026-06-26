"""Embedding service — generate dense vectors via Ollama or OpenAI.

Public API
----------
embed_text(text: str) -> list[float] | None
    Embed a single string. Returns None on failure (caller decides fallback).

embed_batch(texts: list[str]) -> list[list[float]]
    Embed a list of strings. Returns empty list on total failure.
    Partial failures return a list of the successfully-embedded vectors.

Fix (2025-06-26)
----------------
Both functions previously swallowed ALL exceptions and returned None / []
with no log emission at ERROR level. A misconfigured Ollama model or a
transient network partition caused every vector search to silently return
empty results with zero observability. Fixed: log at ERROR with exc_info
before returning the fallback value so operators can see and act on failures.
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
