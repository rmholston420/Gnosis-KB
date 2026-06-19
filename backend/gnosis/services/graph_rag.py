"""LightRAG integration for dual-level graph-aware retrieval.

LightRAG automatically extracts entities and relationships from notes
during ingestion and builds a knowledge graph on top of the vector index.

Three query modes:
  - local:   specific entity lookups
  - global:  thematic synthesis across all notes
  - hybrid:  combines local + global (default for chat)

Entity types tuned to knowledge base domain:
  concept, person, organization, project, tool, technique, insight, question
"""

import logging
from typing import Optional

from gnosis.config import get_settings

logger = logging.getLogger(__name__)

_rag: Optional[object] = None


async def init_lightrag() -> None:
    """Initialize LightRAG with Ollama backend.

    Must be called once at application startup (from lifespan handler).
    Gracefully degrades if Ollama is not running.
    """
    global _rag
    settings = get_settings()

    try:
        from lightrag import LightRAG  # type: ignore[import-untyped]
        from lightrag.llm.ollama import ollama_model_complete, ollama_embed  # type: ignore[import-untyped]
        from lightrag.utils import EmbeddingFunc  # type: ignore[import-untyped]
        import os

        os.makedirs(settings.lightrag_working_dir, exist_ok=True)

        _rag = LightRAG(
            working_dir=settings.lightrag_working_dir,
            llm_model_func=ollama_model_complete,
            llm_model_name=settings.ollama_llm_model,
            llm_model_kwargs={"host": settings.ollama_base_url, "options": {"num_ctx": 32768}},
            embedding_func=EmbeddingFunc(
                embedding_dim=768,
                max_token_size=512,
                func=lambda texts: ollama_embed(
                    texts,
                    embed_model=settings.ollama_embed_model,
                    host=settings.ollama_base_url,
                ),
            ),
            entity_types=[
                "concept", "person", "organization", "project",
                "tool", "technique", "insight", "question",
            ],
        )
        logger.info("LightRAG initialized with model: %s", settings.ollama_llm_model)
    except Exception as e:
        logger.warning(
            "LightRAG init failed — AI chat will be degraded. Error: %s", e
        )
        _rag = None


async def ingest_note(note_id: str, title: str, body: str) -> None:
    """Ingest a note into LightRAG for graph-aware retrieval.

    Called after a note is created or updated.

    Args:
        note_id: Note primary key (for logging).
        title: Note title.
        body: Note body Markdown text.
    """
    if _rag is None:
        logger.debug("LightRAG not initialized; skipping ingest for %s", note_id)
        return
    try:
        text = f"# {title}\n\n{body}"
        await _rag.ainsert(text)  # type: ignore[union-attr]
        logger.debug("LightRAG ingested note %s", note_id)
    except Exception as e:
        logger.warning("LightRAG ingest failed for note %s: %s", note_id, e)


async def query_vault(question: str, mode: str = "hybrid") -> str:
    """Query the knowledge graph using LightRAG.

    Args:
        question: Natural language question about the vault.
        mode: LightRAG query mode: 'local', 'global', or 'hybrid'.

    Returns:
        LightRAG response string, or a fallback message if unavailable.
    """
    if _rag is None:
        return (
            "LightRAG is not available. Please ensure Ollama is running and "
            "the LLM model is configured correctly."
        )
    try:
        from lightrag import QueryParam  # type: ignore[import-untyped]
        result = await _rag.aquery(question, param=QueryParam(mode=mode))  # type: ignore[union-attr]
        return str(result)
    except Exception as e:
        logger.error("LightRAG query failed: %s", e)
        return f"Query failed: {e}"
