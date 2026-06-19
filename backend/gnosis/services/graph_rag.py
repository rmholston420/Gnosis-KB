"""
LightRAG integration for dual-level graph-aware retrieval.

Query modes:
  local  — specific entity lookups ("what does note X say about Y?")
  global — thematic synthesis ("recurring themes in my EEG notes?")
  hybrid — combines both (default for /ai/chat endpoint)

Namespace contract
------------------
Each user gets their own LightRAG working directory:

    LIGHTRAG_DATA_DIR/<user_id>/

This means the knowledge graph, entity store, and vector cache are
completely isolated per user.  ``user_id=0`` (sentinel) is reserved
for the legacy single-user global graph created before multi-user
support was added — callers using the old API surface will transparently
continue to use that directory.

Instances are lazily initialised and cached in ``_instances`` keyed by
``user_id``, so the overhead of re-init on every request is avoided.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from gnosis.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Sentinel user_id for the legacy global graph
_LEGACY_USER_ID = 0

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
    """Wraps per-user LightRAG lifecycle and exposes ingest / query helpers.

    Each ``user_id`` maps to its own LightRAG instance backed by a
    separate on-disk working directory, providing complete graph isolation
    between vaults.

    Usage::

        await graph_rag.ingest_note(user_id=42, title="My Note", body="...")
        answer = await graph_rag.query(user_id=42, question="...")
    """

    def __init__(self) -> None:
        # { user_id: LightRAG instance }
        self._instances: Dict[int, Any] = {}
        self._base_dir = Path(settings.lightrag_data_dir)

    def _working_dir(self, user_id: int) -> Path:
        """Return the per-user LightRAG working directory.

        The legacy global graph lives directly in ``lightrag_data_dir``
        (user_id == 0) so existing data is not orphaned.
        """
        if user_id == _LEGACY_USER_ID:
            return self._base_dir
        return self._base_dir / str(user_id)

    async def _get_instance(self, user_id: int) -> Any:
        """Return the LightRAG instance for *user_id*, initialising if needed.

        Args:
            user_id: Owner's user ID (use 0 for legacy global graph).

        Returns:
            Initialised LightRAG instance, or ``None`` if LightRAG is
            unavailable.
        """
        if not _LIGHTRAG_AVAILABLE:
            return None

        if user_id in self._instances:
            return self._instances[user_id]

        working_dir = self._working_dir(user_id)
        working_dir.mkdir(parents=True, exist_ok=True)

        try:
            instance = LightRAG(
                working_dir=str(working_dir),
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
            self._instances[user_id] = instance
            logger.info(
                "GraphRAGService: LightRAG initialised for user %s at %s",
                user_id,
                working_dir,
            )
            return instance
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "GraphRAGService: LightRAG init failed for user %s: %s", user_id, exc
            )
            return None

    async def initialize(self, user_id: int = _LEGACY_USER_ID) -> None:
        """Pre-warm the LightRAG instance for *user_id*.

        Called on application startup for the legacy global graph
        (``user_id=0``).  Per-user instances are initialised lazily on
        first ``ingest_note`` / ``query`` call.

        Args:
            user_id: User ID to pre-warm (default: legacy global).
        """
        await self._get_instance(user_id)

    def is_available(self, user_id: int = _LEGACY_USER_ID) -> bool:
        """Return True when LightRAG is installed and ready for *user_id*."""
        return _LIGHTRAG_AVAILABLE and user_id in self._instances

    async def ingest_note(
        self,
        title: str,
        body: str,
        user_id: int = _LEGACY_USER_ID,
    ) -> None:
        """Ingest a note into *user_id*'s LightRAG knowledge graph.

        Args:
            title: Note title prepended to the body for context.
            body: Markdown body of the note.
            user_id: Owner's user ID.  Defaults to legacy global graph.
        """
        instance = await self._get_instance(user_id)
        if instance is None:
            return
        try:
            await instance.ainsert(f"{title}\n\n{body}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "GraphRAGService.ingest_note failed for user %s: %s", user_id, exc
            )

    async def query(
        self,
        question: str,
        user_id: int = _LEGACY_USER_ID,
        mode: str = "hybrid",
    ) -> str:
        """Query *user_id*'s knowledge graph.

        Args:
            question: Natural language question.
            user_id: Owner's user ID.  Defaults to legacy global graph.
            mode: One of 'local', 'global', or 'hybrid'.

        Returns:
            Answer string from LightRAG, or a fallback message.
        """
        instance = await self._get_instance(user_id)
        if instance is None:
            return (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )
        try:
            return await instance.aquery(question, param=QueryParam(mode=mode))
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "GraphRAGService.query failed for user %s: %s", user_id, exc
            )
            return f"Query failed: {exc}"


# Module-level singleton — shared across the application lifetime
graph_rag = GraphRAGService()
