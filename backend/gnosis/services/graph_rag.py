"""
LightRAG integration for dual-level graph-aware retrieval.

Query modes:
  local  — specific entity lookups ("what does note X say about Y?")
  global — thematic synthesis ("recurring themes in my EEG notes?")
  hybrid — combines both (default for /ai/chat endpoint)

Namespace contract
------------------
Each user gets their own LightRAG working directory::

    LIGHTRAG_DATA_DIR/<user_id>/

This means the knowledge graph, entity store, and vector cache are
completely isolated per user.  ``user_id=0`` (sentinel) is reserved
for the legacy single-user global graph created before multi-user
support was added — callers using the old API surface will transparently
continue to use that directory.

Instances are lazily initialised and cached in ``_instances`` keyed by
``user_id``, so the overhead of re-init on every request is avoided.

Shared-vault reads
------------------
When ``owner_ids`` contains IDs beyond the caller's own ``user_id``,
``query()`` fans out to each accessible user's LightRAG instance and
merges the answers via a lightweight LLM synthesis call.  ``stream()``
yields the caller's own graph tokens first, then appends a merged
synthesis block from shared vaults as a final chunk.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from gnosis.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_LEGACY_USER_ID = 0

try:
    from lightrag import LightRAG, QueryParam  # type: ignore[import]
    from lightrag.llm.ollama import ollama_embed, ollama_model_complete  # type: ignore[import]

    _LIGHTRAG_AVAILABLE = True
except ImportError:
    _LIGHTRAG_AVAILABLE = False
    logger.warning(
        "lightrag-hku not installed — graph-RAG chat will fall back to plain LLM completion."
    )


class GraphRAGService:
    """Wraps per-user LightRAG lifecycle and exposes ingest / query / stream helpers.

    Each ``user_id`` maps to its own LightRAG instance backed by a
    separate on-disk working directory, providing complete graph isolation
    between vaults.

    Shared-vault members receive merged answers from all accessible graphs
    when ``owner_ids`` is passed to ``query()`` or ``stream()``.
    """

    def __init__(self) -> None:
        self._instances: dict[int, Any] = {}
        self._base_dir = Path(settings.lightrag_data_dir)

    def _working_dir(self, user_id: int) -> Path:
        if user_id == _LEGACY_USER_ID:
            return self._base_dir
        return self._base_dir / str(user_id)

    async def _get_instance(self, user_id: int) -> Any:
        """Return the LightRAG instance for *user_id*, initialising if needed."""
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
                    "concept", "person", "project", "tool",
                    "technique", "insight", "question",
                ],
            )
            self._instances[user_id] = instance
            logger.info(
                "GraphRAGService: LightRAG initialised for user %s at %s",
                user_id, working_dir,
            )
            return instance
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "GraphRAGService: LightRAG init failed for user %s: %s", user_id, exc
            )
            return None

    async def initialize(self, user_id: int = _LEGACY_USER_ID) -> None:
        """Pre-warm the LightRAG instance for *user_id* (called at startup)."""
        await self._get_instance(user_id)

    async def is_available(self, user_id: int = _LEGACY_USER_ID) -> bool:  # type: ignore[override]
        """Return True when LightRAG is installed and the instance for *user_id* is ready.

        Promoted to async so callers can ``await graph_rag.is_available(id)``
        consistently.  The check itself is synchronous but the coroutine
        wrapper keeps the call-site pattern uniform.
        """
        return _LIGHTRAG_AVAILABLE and user_id in self._instances

    async def ingest_note(
        self,
        title: str,
        body: str,
        user_id: int = _LEGACY_USER_ID,
    ) -> None:
        """Ingest a note into *user_id*'s LightRAG knowledge graph."""
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
        owner_ids: set[int] | None = None,
    ) -> str:
        """Query the knowledge graph(s) accessible to *user_id*.

        When *owner_ids* contains IDs beyond *user_id* (i.e., the caller has
        shared-vault grants), this method fans out the question to each
        accessible user's LightRAG instance and synthesises the answers into
        a single coherent response.

        Args:
            question: Natural language question.
            user_id: The caller's own user ID.
            mode: One of 'local', 'global', or 'hybrid'.
            owner_ids: Full set of accessible vault owner IDs.  When None or
                equal to ``{user_id}``, only the caller's own graph is queried.

        Returns:
            Answer string, synthesised across all accessible graphs.
        """
        # Determine which user graphs to query
        target_ids: set[int] = owner_ids or {user_id}
        # Always include the caller's own ID
        target_ids = target_ids | {user_id}

        # Single-graph fast path (most common case)
        if len(target_ids) == 1:
            return await self._query_single(user_id, question, mode)

        # Multi-graph fan-out
        answers: list[str] = []
        for uid in sorted(target_ids):
            answer = await self._query_single(uid, question, mode)
            if answer and not answer.startswith("Graph-RAG is unavailable") and not answer.startswith("Query failed"):
                answers.append(f"[Vault {uid}]\n{answer}")

        if not answers:
            return (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )

        if len(answers) == 1:
            return answers[0].split("\n", 1)[1]  # strip the [Vault N] header

        # Synthesise multiple vault answers via LLM
        return await self._synthesise(question, answers)

    async def _query_single(self, user_id: int, question: str, mode: str) -> str:
        """Query one user's LightRAG instance."""
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

    async def _synthesise(self, question: str, answers: list[str]) -> str:
        """Merge answers from multiple vaults into one coherent response.

        Uses the llm_provider directly so we don't need a LightRAG instance
        for synthesis — just a lightweight LLM call.
        """
        from gnosis.services.llm_provider import llm_provider  # local import avoids circular dep

        if not llm_provider.is_available:
            # Fall back to concatenation if LLM is also unavailable
            return "\n\n---\n\n".join(answers)

        joined = "\n\n---\n\n".join(answers)
        prompt = (
            f"Question: {question}\n\n"
            f"Answers from multiple knowledge vaults:\n\n{joined}\n\n"
            "Synthesise these answers into a single coherent, non-repetitive response. "
            "Preserve all unique insights. Do not mention vault numbers in the output."
        )
        try:
            return await llm_provider.complete(prompt, temperature=0.2)
        except Exception as exc:  # noqa: BLE001
            logger.warning("GraphRAGService._synthesise LLM call failed: %s", exc)
            return "\n\n---\n\n".join(answers)

    async def stream(
        self,
        question: str,
        user_id: int = _LEGACY_USER_ID,
        mode: str = "hybrid",
        owner_ids: set[int] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream an answer token-by-token from *user_id*'s knowledge graph.

        For shared-vault callers (``owner_ids`` contains extra IDs), the
        caller's own graph is streamed first, then a synthesised block from
        the remaining vaults is appended as a final non-streamed chunk.  True
        token-level interleaving across multiple LightRAG instances is not
        supported; this approach keeps latency low for the common single-vault
        case.

        Args:
            question: Natural language question.
            user_id: The caller's own user ID.
            mode: One of 'local', 'global', or 'hybrid'.
            owner_ids: Full set of accessible vault owner IDs.

        Yields:
            String tokens as they arrive from LightRAG.
        """
        instance = await self._get_instance(user_id)
        if instance is None:
            yield (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )
            return

        # Stream primary user's graph
        try:
            if hasattr(instance, "astream_query"):
                async for token in instance.astream_query(question, param=QueryParam(mode=mode)):
                    yield token
            else:
                # LightRAG version doesn't support streaming — yield as single token
                result = await instance.aquery(question, param=QueryParam(mode=mode))
                yield result
        except Exception as exc:  # noqa: BLE001
            logger.error("GraphRAGService.stream failed for user %s: %s", user_id, exc)
            yield f"Stream error: {exc}"
            return

        # Append merged shared-vault context if applicable
        shared_ids = (owner_ids or set()) - {user_id}
        if not shared_ids:
            return

        shared_answers: list[str] = []
        for uid in sorted(shared_ids):
            answer = await self._query_single(uid, question, mode)
            if answer and not answer.startswith("Graph-RAG is unavailable") and not answer.startswith("Query failed"):
                shared_answers.append(f"[Vault {uid}]\n{answer}")

        if shared_answers:
            synthesis = await self._synthesise(question, shared_answers)
            yield "\n\n--- *Additional context from shared vaults:*\n\n"
            yield synthesis


# Module-level singleton — shared across the application lifetime
graph_rag = GraphRAGService()
