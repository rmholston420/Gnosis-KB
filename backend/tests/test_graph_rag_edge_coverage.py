"""Coverage-focused tests for gnosis/services/graph_rag.py edge branches."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_service(base_dir: str = "/tmp/lightrag_edge"):
    from gnosis.services.graph_rag import GraphRAGService

    svc = GraphRAGService.__new__(GraphRAGService)
    svc._instances = {}
    svc._base_dir = Path(base_dir)
    return svc


@pytest.mark.asyncio
async def test_get_instance_initializes_and_caches_instance(tmp_path):
    from gnosis.services import graph_rag as mod

    svc = _make_service(str(tmp_path))
    fake_instance = object()

    with (
        patch.object(mod, "_LIGHTRAG_AVAILABLE", True),
        patch.object(mod, "LightRAG", return_value=fake_instance, create=True) as mock_cls,
        patch.object(mod, "ollama_model_complete", object(), create=True),
        patch.object(mod, "ollama_embed", object(), create=True),
    ):
        inst1 = await svc._get_instance(42)
        inst2 = await svc._get_instance(42)

    assert inst1 is fake_instance
    assert inst2 is fake_instance
    assert svc._instances[42] is fake_instance
    mock_cls.assert_called_once()
    assert (tmp_path / "42").exists()


@pytest.mark.asyncio
async def test_get_instance_returns_none_when_lightrag_init_fails(tmp_path):
    from gnosis.services import graph_rag as mod

    svc = _make_service(str(tmp_path))

    with (
        patch.object(mod, "_LIGHTRAG_AVAILABLE", True),
        patch.object(mod, "LightRAG", side_effect=RuntimeError("init failed"), create=True),
        patch.object(mod, "ollama_model_complete", object(), create=True),
        patch.object(mod, "ollama_embed", object(), create=True),
    ):
        inst = await svc._get_instance(7)

    assert inst is None
    assert 7 not in svc._instances


@pytest.mark.asyncio
async def test_initialize_calls_get_instance():
    svc = _make_service()

    with patch.object(svc, "_get_instance", new=AsyncMock(return_value="inst")) as mock_get:
        await svc.initialize(user_id=5)

    mock_get.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_synthesise_falls_back_when_llm_complete_raises():
    svc = _make_service()
    answers = ["[Vault 1]\nA", "[Vault 2]\nB"]

    fake_llm = MagicMock()
    fake_llm.is_available = True
    fake_llm.complete = AsyncMock(side_effect=RuntimeError("llm down"))

    with patch("gnosis.services.llm_provider.llm_provider", fake_llm):
        result = await svc._synthesise("question?", answers)

    assert "[Vault 1]" in result
    assert "[Vault 2]" in result


@pytest.mark.asyncio
async def test_stream_appends_shared_vault_synthesis_when_present():
    svc = _make_service()
    primary = MagicMock()

    async def _astream_query(*args, **kwargs):
        yield "primary-token"

    primary.astream_query = _astream_query

    with (
        patch.object(svc, "_get_instance", new=AsyncMock(return_value=primary)),
        patch.object(svc, "_query_single", new=AsyncMock(return_value="shared answer")),
        patch.object(svc, "_synthesise", new=AsyncMock(return_value="merged shared context")),
        patch("gnosis.services.graph_rag.QueryParam", MagicMock(), create=True),
    ):
        chunks = []
        async for chunk in svc.stream("q", user_id=1, owner_ids={1, 2}, mode="hybrid"):
            chunks.append(chunk)

    joined = "".join(chunks)
    assert "primary-token" in joined
    assert "Additional context from shared vaults" in joined
    assert "merged shared context" in joined
