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
    """Wraps per-user LightRAG lifecycle and exposes ingest / query / stream helpers."""

    def __init__(self) -> None:
        self._instances: dict[int, Any] = {}
        self._base_dir = Path(getattr(settings, "lightrag_data_dir", "/tmp/lightrag"))

    def _working_dir(self, user_id: int) -> Path:
        if user_id == _LEGACY_USER_ID:
            return self._base_dir
        return self._base_dir / str(user_id)

    async def _get_instance(self, user_id: int) -> Any:
        """Return the LightRAG instance for *user_id*, initialising if needed.

        Guarantees
        ----------
        - Never raises; returns ``None`` on any failure.
        - If init fails, ``user_id`` is removed from ``_instances`` so the
          next call will retry rather than returning a stale entry.
        """
        if not _LIGHTRAG_AVAILABLE:
            return None
        if user_id in self._instances:
            return self._instances[user_id]

        try:
            working_dir = self._working_dir(user_id)
            working_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "GraphRAGService: could not create working dir for user %s: %s", user_id, exc
            )
            return None

        instance: Any = None
        try:
            instance = LightRAG(
                working_dir=str(working_dir),
                llm_model_func=ollama_model_complete,
                llm_model_name=getattr(settings, "ollama_llm_model", "llama3.2"),
                embedding_func=ollama_embed,
                embedding_model=getattr(settings, "ollama_embed_model", "nomic-embed-text"),
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
            # Remove any partially-inserted entry so subsequent calls retry cleanly.
            self._instances.pop(user_id, None)
            logger.error(
                "GraphRAGService: LightRAG init failed for user %s: %s", user_id, exc
            )
            return None

    async def initialize(self, user_id: int = _LEGACY_USER_ID) -> None:
        """Pre-warm the LightRAG instance for *user_id* (called at startup)."""
        await self._get_instance(user_id)

    async def is_available(self, user_id: int = _LEGACY_USER_ID) -> bool:
        """Return True when LightRAG is installed and the instance for *user_id* is ready."""
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
            logger.warning("GraphRAGService.ingest_note failed for user %s: %s", user_id, exc)

    async def export_graph(self, owner_ids: list[int]) -> dict[str, Any]:
        """Export the LightRAG entity/relation graph for the given owner_ids."""
        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []

        for uid in owner_ids:
            instance = await self._get_instance(uid)
            if instance is None:
                continue
            try:
                if hasattr(instance, "chunk_entity_relation_graph"):
                    graph = instance.chunk_entity_relation_graph
                    for node_id, data in graph.nodes(data=True):
                        nodes.append(
                            {
                                "id": str(node_id),
                                "label": data.get("entity_name", str(node_id)),
                                "description": data.get("description"),
                                "cluster": data.get("source_id"),
                                "source_note_ids": [],
                            }
                        )
                    for src, tgt, edata in graph.edges(data=True):
                        links.append(
                            {
                                "source": str(src),
                                "target": str(tgt),
                                "label": edata.get("keywords", ""),
                            }
                        )
                else:
                    import json

                    wd = self._working_dir(uid)
                    entities_file = wd / "entities.json"
                    relations_file = wd / "relations.json"
                    if entities_file.exists():
                        raw = json.loads(entities_file.read_text())
                        for eid, edata in raw.items() if isinstance(raw, dict) else enumerate(raw):
                            nodes.append(
                                {
                                    "id": str(eid),
                                    "label": edata.get("entity_name", str(eid))
                                    if isinstance(edata, dict)
                                    else str(edata),
                                    "description": edata.get("description")
                                    if isinstance(edata, dict)
                                    else None,
                                    "cluster": None,
                                    "source_note_ids": [],
                                }
                            )
                    if relations_file.exists():
                        raw_rels = json.loads(relations_file.read_text())
                        for rel in raw_rels if isinstance(raw_rels, list) else []:
                            links.append(
                                {
                                    "source": str(rel.get("src_id", "")),
                                    "target": str(rel.get("tgt_id", "")),
                                    "label": rel.get("keywords", ""),
                                }
                            )
            except Exception as exc:  # noqa: BLE001
                logger.warning("export_graph failed for user %s: %s", uid, exc)

        return {"nodes": nodes, "links": links}

    async def query(
        self,
        question: str,
        user_id: int = _LEGACY_USER_ID,
        mode: str = "hybrid",
        owner_ids: set[int] | None = None,
    ) -> str:
        """Query the knowledge graph(s) accessible to *user_id*."""
        target_ids: set[int] = owner_ids or {user_id}
        target_ids = target_ids | {user_id}

        if len(target_ids) == 1:
            return await self._query_single(user_id, question, mode)

        answers: list[str] = []
        for uid in sorted(target_ids):
            answer = await self._query_single(uid, question, mode)
            if (
                answer
                and not answer.startswith("Graph-RAG is unavailable")
                and not answer.startswith("Query failed")
            ):
                answers.append(f"[Vault {uid}]\n{answer}")

        if not answers:
            return (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )

        if len(answers) == 1:
            return answers[0].split("\n", 1)[1]

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
            logger.error("GraphRAGService.query failed for user %s: %s", user_id, exc)
            return f"Query failed: {exc}"

    async def _synthesise(self, question: str, answers: list[str]) -> str:
        """Merge answers from multiple vaults into one coherent response."""
        from gnosis.services.llm_provider import llm_provider

        if not llm_provider.is_available:
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
        """Stream an answer token-by-token from *user_id*'s knowledge graph."""
        instance = await self._get_instance(user_id)
        if instance is None:
            yield (
                "Graph-RAG is unavailable (LightRAG not initialised). "
                "Ensure Ollama is running and lightrag-hku is installed."
            )
            return

        try:
            if hasattr(instance, "astream_query"):
                async for token in instance.astream_query(question, param=QueryParam(mode=mode)):
                    yield token
            else:
                result = await instance.aquery(question, param=QueryParam(mode=mode))
                yield result
        except Exception as exc:  # noqa: BLE001
            logger.error("GraphRAGService.stream failed for user %s: %s", user_id, exc)
            yield f"Stream error: {exc}"
            return

        shared_ids = (owner_ids or set()) - {user_id}
        if not shared_ids:
            return

        shared_answers: list[str] = []
        for uid in sorted(shared_ids):
            answer = await self._query_single(uid, question, mode)
            if (
                answer
                and not answer.startswith("Graph-RAG is unavailable")
                and not answer.startswith("Query failed")
            ):
                shared_answers.append(f"[Vault {uid}]\n{answer}")

        if shared_answers:
            synthesis = await self._synthesise(question, shared_answers)
            yield "\n\n--- *Additional context from shared vaults:*\n\n"
            yield synthesis


# Module-level singleton — shared across the application lifetime
graph_rag = GraphRAGService()
