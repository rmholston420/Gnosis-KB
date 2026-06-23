"""
Targeted gap coverage for the four services still at 95-99%.

All async tests use @pytest.mark.asyncio + async def so pytest-asyncio's
event loop is used correctly. No asyncio.get_event_loop() calls.

Missing lines addressed
-----------------------
graph_rag.py    : 50-52  _LIGHTRAG_AVAILABLE=False branch
                  187    _synthesise fallback when llm not available
                  288/291 stream: early return when shared_ids empty / error path
llm_provider.py : 41->52  initialize: Ollama non-200 / exception skip
                  112/114  active_model groq / openai branches
                  125      swap_model RuntimeError when ollama absent
                  181->179 stream: all providers fail -> RuntimeError
vault_sync.py   : 152->156  run_full_sync: vault does not exist
                  168->163  run_full_sync: per-file exception in loop
                  254-259   _handle_upsert exception path
                  311-312   start_vault_watcher startup-sync exception
vector_store.py : 156->158  get_qdrant_client: _client already set (returns early)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ===========================================================================
# graph_rag.py
# ===========================================================================

class TestGraphRAGAvailabilityFlag:
    """Lines 50-52: _LIGHTRAG_AVAILABLE is set correctly at import time."""

    def test_flag_is_bool(self):
        import gnosis.services.graph_rag as gr
        assert isinstance(gr._LIGHTRAG_AVAILABLE, bool)

    @pytest.mark.asyncio
    async def test_get_instance_returns_none_when_unavailable(self):
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.graph_rag as gr

        svc = GraphRAGService()
        original = gr._LIGHTRAG_AVAILABLE
        try:
            gr._LIGHTRAG_AVAILABLE = False
            result = await svc._get_instance(99)
            assert result is None
        finally:
            gr._LIGHTRAG_AVAILABLE = original


class TestGraphRAGSynthesise:
    """Line 187: _synthesise fallback when llm_provider unavailable or raises."""

    @pytest.mark.asyncio
    async def test_synthesise_llm_unavailable_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        answers = ["[Vault 1]\nanswer one", "[Vault 2]\nanswer two"]

        with patch("gnosis.services.graph_rag.llm_provider") as mock_llm:
            type(mock_llm).is_available = PropertyMock(return_value=False)
            result = await svc._synthesise("q", answers)

        assert "answer one" in result
        assert "answer two" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_synthesise_llm_raises_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        answers = ["[Vault 1]\nfoo", "[Vault 2]\nbar"]

        with patch("gnosis.services.graph_rag.llm_provider") as mock_llm:
            type(mock_llm).is_available = PropertyMock(return_value=True)
            mock_llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
            result = await svc._synthesise("q", answers)

        assert "foo" in result
        assert "bar" in result


class TestGraphRAGStream:
    """Lines 288->286 / 291->exit: stream early-return and error paths."""

    @pytest.mark.asyncio
    async def test_stream_no_shared_ids_returns_single_token(self):
        """owner_ids == {user_id}: shared_ids is empty, stream exits after own graph."""
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        mock_instance = MagicMock()
        mock_instance.aquery = AsyncMock(return_value="answer text")
        # No astream_query attribute -> falls back to aquery single-token path
        if hasattr(mock_instance, "astream_query"):
            del mock_instance.astream_query

        tokens = []
        with patch.object(svc, "_get_instance", return_value=mock_instance):
            async for tok in svc.stream("question", user_id=1, owner_ids={1}):
                tokens.append(tok)

        assert tokens == ["answer text"]

    @pytest.mark.asyncio
    async def test_stream_instance_none_yields_unavailable(self):
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        tokens = []
        with patch.object(svc, "_get_instance", return_value=None):
            async for tok in svc.stream("q", user_id=1):
                tokens.append(tok)

        assert any("unavailable" in t.lower() for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_aquery_raises_yields_error_token(self):
        """Line 291: exception during streaming yields error string then returns."""
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        mock_instance = MagicMock()
        mock_instance.aquery = AsyncMock(side_effect=RuntimeError("gpu oom"))
        # Force the no-astream_query fallback path
        try:
            del mock_instance.astream_query
        except AttributeError:
            pass
        # Make hasattr return False for astream_query
        mock_instance.__dict__.pop("astream_query", None)
        type(mock_instance).astream_query = property(lambda self: (_ for _ in ()).throw(AttributeError()))

        tokens = []
        with patch.object(svc, "_get_instance", return_value=mock_instance):
            with patch("builtins.hasattr", wraps=lambda obj, name: (
                False if (obj is mock_instance and name == "astream_query") else hasattr.__wrapped__(obj, name)
                    if hasattr(hasattr, "__wrapped__") else True
            )):
                async for tok in svc.stream("q", user_id=1):
                    tokens.append(tok)

        # aquery raises -> except branch -> yield "Stream error: ..."
        assert any("error" in t.lower() or "stream" in t.lower() for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_exception_via_astream_query(self):
        """stream: astream_query raises -> except block -> yield error."""
        from gnosis.services.graph_rag import GraphRAGService

        svc = GraphRAGService()
        mock_instance = MagicMock()

        async def _bad_stream(*a, **kw):
            raise RuntimeError("stream fail")
            yield  # make it an async generator

        mock_instance.astream_query = _bad_stream

        tokens = []
        with patch.object(svc, "_get_instance", return_value=mock_instance):
            async for tok in svc.stream("q", user_id=1):
                tokens.append(tok)

        assert any("error" in t.lower() or "fail" in t.lower() for t in tokens)


# ===========================================================================
# llm_provider.py
# ===========================================================================

class TestLLMProviderActiveModel:
    """Lines 112, 114: active_model groq / openai branches."""

    def test_active_model_groq(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["groq"]
        assert p.active_model == "llama-3.3-70b-versatile"

    def test_active_model_openai(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["openai"]
        assert p.active_model == "gpt-4o-mini"

    def test_active_model_none(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = []
        assert p.active_model == ""


class TestLLMProviderSwapModel:
    """Line 125: swap_model raises when ollama not available."""

    def test_swap_model_no_ollama_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["groq"]
        with pytest.raises(RuntimeError, match="Ollama is not an available provider"):
            p.swap_model("llama3.2")

    def test_swap_model_with_ollama_succeeds(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["ollama"]
        p._ollama_client = MagicMock()
        p.swap_model("mistral")
        assert p._ollama_model == "mistral"


class TestLLMProviderInitialize:
    """Line 41->52: Ollama HTTP non-200 / exception skips adding to _available."""

    @pytest.mark.asyncio
    async def test_initialize_ollama_non_200_skips(self):
        from gnosis.services.llm_provider import LLMProvider

        p = LLMProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_resp)
        # httpx.AsyncClient is used as `async with AsyncClient(...) as client:`
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.services.llm_provider.httpx.AsyncClient", return_value=mock_context):
            with patch("gnosis.services.llm_provider.settings") as s:
                s.ollama_base_url = "http://localhost:11434"
                s.groq_api_key = ""
                s.openai_api_key = ""
                s.ollama_llm_model = "llama3.2"
                await p.initialize()

        assert "ollama" not in p._available

    @pytest.mark.asyncio
    async def test_initialize_ollama_exception_skips(self):
        from gnosis.services.llm_provider import LLMProvider

        p = LLMProvider()
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.services.llm_provider.httpx.AsyncClient", return_value=mock_context):
            with patch("gnosis.services.llm_provider.settings") as s:
                s.ollama_base_url = "http://localhost:11434"
                s.groq_api_key = ""
                s.openai_api_key = ""
                s.ollama_llm_model = "llama3.2"
                await p.initialize()

        assert "ollama" not in p._available


class TestLLMProviderStreamAllFail:
    """Line 181->179: all stream providers fail -> RuntimeError."""

    @pytest.mark.asyncio
    async def test_stream_all_providers_fail_raises(self):
        from gnosis.services.llm_provider import LLMProvider

        p = LLMProvider()
        p._available = ["ollama"]
        p._ollama_model = "llama3.2"

        # Build a mock client whose chat.completions.create raises
        mock_create = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_completions = MagicMock()
        mock_completions.create = mock_create
        mock_chat = MagicMock()
        mock_chat.completions = mock_completions
        mock_ollama_client = MagicMock()
        mock_ollama_client.chat = mock_chat
        p._ollama_client = mock_ollama_client

        with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
            async for _ in p.stream("hello"):
                pass


# ===========================================================================
# vault_sync.py
# ===========================================================================

class TestVaultSyncRunFullSync:
    """Lines 152->156, 168->163: missing vault and per-file exception in loop."""

    @pytest.mark.asyncio
    async def test_run_full_sync_missing_vault_yields_error(self, tmp_path):
        from gnosis.services.vault_sync import run_full_sync_for_user

        non_existent = tmp_path / "does_not_exist"
        lines = []
        with patch("gnosis.services.vault_sync._get_vault_path", return_value=non_existent):
            with patch("gnosis.services.vault_sync._resolve_owner_id",
                       new=AsyncMock(return_value=1)):
                async for line in run_full_sync_for_user(1):
                    lines.append(line)

        assert any("error" in l for l in lines)
        assert any("does not exist" in l for l in lines)

    @pytest.mark.asyncio
    async def test_run_full_sync_file_exception_yields_error_line(self, tmp_path):
        from gnosis.services.vault_sync import run_full_sync_for_user

        (tmp_path / "note.md").write_text("---\ntitle: t\n---\nbody")

        mock_session = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        lines = []
        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync._resolve_owner_id",
                       new=AsyncMock(return_value=1)):
                with patch("gnosis.services.vault_sync._sync_file",
                           new=AsyncMock(side_effect=RuntimeError("parse fail"))):
                    with patch("gnosis.services.vault_sync.AsyncSessionFactory",
                               return_value=mock_cm):
                        async for line in run_full_sync_for_user(1):
                            lines.append(line)

        assert any("error" in l for l in lines)


class TestVaultEventHandlerUpsert:
    """Lines 254-259: _handle_upsert exception is caught, not re-raised."""

    @pytest.mark.asyncio
    async def test_handle_upsert_exception_is_swallowed(self, tmp_path):
        from gnosis.services.vault_sync import VaultEventHandler

        handler = VaultEventHandler(owner_id=1)
        test_path = tmp_path / "note.md"
        test_path.write_text("---\ntitle: Test\n---\nbody")

        mock_session = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
            with patch("gnosis.services.vault_sync._sync_file",
                       new=AsyncMock(side_effect=RuntimeError("db down"))):
                # Must not raise
                await handler._handle_upsert(test_path)


class TestStartVaultWatcherException:
    """Lines 311-312: start_vault_watcher catches startup-sync exception."""

    @pytest.mark.asyncio
    async def test_start_vault_watcher_sync_exception_logged(self, tmp_path):
        from gnosis.services.vault_sync import start_vault_watcher

        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()

        async def _bad_sync(owner_id):
            raise RuntimeError("sync boom")
            yield  # make it an async generator signature

        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync.run_full_sync_for_user", side_effect=RuntimeError("sync boom")):
                with patch("gnosis.services.vault_sync.Observer", return_value=mock_observer):
                    observer = await start_vault_watcher(owner_id=1)

        assert observer is mock_observer


# ===========================================================================
# vector_store.py — line 156->158: get_qdrant_client returns cached _client
# ===========================================================================

class TestVectorStoreClientCache:
    """Line 156->158: get_qdrant_client() short-circuits when _client is set."""

    def test_get_qdrant_client_returns_cached_instance(self):
        import gnosis.services.vector_store as vs

        original = vs._client
        mock_client = MagicMock()
        try:
            vs._client = mock_client
            result = vs.get_qdrant_client()
            assert result is mock_client
        finally:
            vs._client = original

    def test_get_qdrant_client_creates_new_when_none(self):
        """Complementary: _client is None -> QdrantClient is constructed."""
        import gnosis.services.vector_store as vs

        original = vs._client
        try:
            vs._client = None
            with patch("gnosis.services.vector_store.QdrantClient") as mock_cls:
                mock_cls.return_value = MagicMock()
                with patch("gnosis.services.vector_store.get_settings") as mock_settings:
                    mock_settings.return_value.qdrant_url = "http://localhost:6333"
                    mock_settings.return_value.qdrant_api_key = None
                    client = vs.get_qdrant_client()
            assert client is mock_cls.return_value
        finally:
            vs._client = original
