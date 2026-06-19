"""
LightRAG integration for dual-level graph-aware retrieval.

Query modes:
  local  — specific entity lookups ("what does note X say about Y?")
  global — thematic synthesis ("recurring themes in my EEG notes?")
  hybrid — combines both (default for /ai/chat endpoint)

The LightRAG working directory persists both the knowledge graph
and the vector cache between restarts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gnosis.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy imports — LightRAG is optional; degrade gracefully if not installed
try:
    from lightrag import LightRAG, QueryParam  # type: ignore[import]
    from lightrag.llm.ollama import ollama_model_complete, ollama_embed  # type: ignore[import]

    _LIGHTRAG_AVAILABLE = True
except ImportError:
    _LIGHTRAG_AVAILABLE = False
    logger.warning(
        "lightrag-hku not installed — graph-RAG chat will fall back to plain LLM completion."
    )


class GraphRAGService:
    """Wraps LightRAG lifecycle and exposes ingest / query helpers."""

    def __init__(self) -> None:
        self._rag: Any = None
        self._working_dir = Path(settings.lightrag_data_dir)

    async def initialize(self) -> None:
        """Initialize LightRAG on application startup."""
        if not _LIGHTRAG_AVAILABLE:
            logger.warning("GraphRAGService: LightRAG unavailable — skipping init")
            return

        self._working_dir.mkdir(parents=True, exist_ok=True)

        try:
            self._rag = LightRAG(
                working_dir=str(self._working_dir),
                llm_model_func=ollama_model_complete,
                llm_model_name=settings.ollama_llm_model,
                embedding_func=ollama_embed,
                embedding_model=settings.ollama_embed_model,
                entity_types=[
                    "concept",
                    "person",
                    "project",
                    "tool",
                    "technique",
                    "insight",
                    "question",
                ],
            )
            logger.info(
                "GraphRAGService: LightRAG initialized at %s", self._working_dir
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("GraphRAGService: LightRAG init failed: %s", exc)
            self._rag = None

    @property
    def is_available(self) -> bool:
        """Return True when LightRAG is initialized and ready."""
        return self._rag is not None

    async def ingest_note(self, title: str, body: str) -> None:
        """Ingest a note into the LightRAG knowledge graph.

        Args:
            title: Note title prepended to the body for context.
            body: Markdown body of the note.
        """
        if not self.is_available:
            return
        try:
            await self._rag.ainsert(f"{title}\n\n{body}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("GraphRAGService.ingest_note failed: %s", exc)

    async def query(
        self, question: str, mode: str = "hybrid"
    ) -> str:
        """Query the knowledge graph.

        Args:
            question: Natural language question.
            mode: One of 'local', 'global', or 'hybrid'.

        Returns:
            Answer string from LightRAG, or a fallback message.
        """
        if not self.is_available:
            return (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )
        try:
            return await self._rag.aquery(question, param=QueryParam(mode=mode))
        except Exception as exc:  # noqa: BLE001
            logger.error("GraphRAGService.query failed: %s", exc)
            return f"Query failed: {exc}"


# Module-level singleton
graph_rag = GraphRAGService()
