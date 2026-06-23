"""
Definitive gap coverage — every uncovered arc addressed with the exact
technique required.

Uncovered arc catalogue
-----------------------
graph_rag.py  50-52   : except ImportError block — lightrag IS installed so
                        this block is dead code at normal import time.  Fix:
                        temporarily remove lightrag from sys.modules and
                        reload the module so the ImportError path executes.
              187     : _synthesise fallback join when llm_provider.is_available
                        is False.  Fix: patch the singleton on its *source*
                        module (gnosis.services.llm_provider.llm_provider)
                        because _synthesise does a local import.
              288->286: False branch of `if not shared_ids` inside stream()
                        — shared_ids is non-empty so execution continues into
                        the for-loop at 290.
              291->exit: `yield synthesis` at the very end of stream(); the
                         generator falls off the end after that yield.

llm_provider  112,114 : active_model groq / openai branches.
              125     : swap_model RuntimeError when ollama absent.
              181->179: `continue` arc in stream() after a provider fails,
                         which loops back to the for statement at 179.
                         Requires TWO providers where the first fails and the
                         second succeeds (or both fail), so the loop-back arc
                         is actually traversed.

vault_sync    152->156: `if not vault_root.exists()` False branch — vault
                        exists, execution falls through to md_files line.
                        Existing happy-path tests already hit this but
                        _VAULT_PATH module cache means the right path is
                        never evaluated from line 152 in those tests.
              168->163: `except Exception` continue arc loops back to for.
              254-259 : _handle_upsert except block.
              311-312 : start_vault_watcher startup-sync except block.

vector_store  156->158: get_qdrant_client() `if _client is None` False branch
                        — _client already set, returns early.
"""
from __future__ import annotations

import sys
import importlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# graph_rag.py  lines 50-52  (ImportError block)
# ===========================================================================

class TestGraphRAGImportError:
    """
    Lines 50-52: the `except ImportError` block runs only when lightrag is
    not importable.  We simulate this by temporarily removing every lightrag
    key from sys.modules and reloading the graph_rag module so the import
    guard fires, then restore the originals.
    """

    def test_lightrag_unavailable_flag_set_false(self):
        # Snapshot and evict
        saved = {k: v for k, v in sys.modules.items() if "lightrag" in k}
        for k in list(saved):
            sys.modules.pop(k, None)

        # Also evict graph_rag so it re-executes its top-level import block
        gr_saved = sys.modules.pop("gnosis.services.graph_rag", None)

        try:
            # Block the import
            sys.modules["lightrag"] = None  # type: ignore[assignment]

            import gnosis.services.graph_rag as gr_fresh
            importlib.reload(gr_fresh)
            assert gr_fresh._LIGHTRAG_AVAILABLE is False
        finally:
            # Restore everything
            for k in list(sys.modules):
                if "lightrag" in k:
                    sys.modules.pop(k, None)
            for k, v in saved.items():
                sys.modules[k] = v
            if gr_saved is not None:
                sys.modules["gnosis.services.graph_rag"] = gr_saved
            else:
                sys.modules.pop("gnosis.services.graph_rag", None)


# ===========================================================================
# graph_rag.py  line 187  (_synthesise fallback)
# ===========================================================================

class TestGraphRAGSynthesise:
    """
    _synthesise does `from gnosis.services.llm_provider import llm_provider`
    as a local import each call.  The correct patch target is the singleton
    on the SOURCE module, not a name in graph_rag (which doesn't exist at
    module scope).
    """

    @pytest.mark.asyncio
    async def test_synthesise_llm_unavailable_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod

        svc = GraphRAGService()
        answers = ["[Vault 1]\nanswer one", "[Vault 2]\nanswer two"]

        real_singleton = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = False
        llm_mod.llm_provider = mock_llm
        try:
            result = await svc._synthesise("q", answers)
        finally:
            llm_mod.llm_provider = real_singleton

        assert "answer one" in result
        assert "answer two" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_synthesise_llm_raises_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod

        svc = GraphRAGService()
        answers = ["[Vault 1]\nfoo", "[Vault 2]\nbar"]

        real_singleton = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
        llm_mod.llm_provider = mock_llm
        try:
            result = await svc._synthesise("q", answers)
        finally:
            llm_mod.llm_provider = real_singleton

        assert "foo" in result
        assert "bar" in result


# ===========================================================================
# graph_rag.py  288->286 and 291->exit  (stream shared-vault path)
# ===========================================================================

class TestGraphRAGStream:

    @pytest.mark.asyncio
    async def test_stream_instance_none_yields_unavailable(self):
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
        tokens = []
        with patch.object(svc, "_get_instance", new_callable=AsyncMock, return_value=None):
            async for tok in svc.stream("q", user_id=1):
                tokens.append(tok)
        assert any("unavailable" in t.lower() for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_no_astream_query_yields_single_token(self):
        """spec=[] makes hasattr(mock, 'astream_query') == False reliably."""
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
        mock_instance = MagicMock(spec=[])  # no auto-attributes
        mock_instance.aquery = AsyncMock(return_value="result text")
        tokens = []
        with patch.object(svc, "_get_instance", new_callable=AsyncMock, return_value=mock_instance):
            async for tok in svc.stream("q", user_id=1, owner_ids={1}):
                tokens.append(tok)
        assert tokens == ["result text"]

    @pytest.mark.asyncio
    async def test_stream_aquery_raises_yields_error(self):
        """Line 291->exit: exception -> yield error token -> return."""
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
        mock_instance = MagicMock(spec=[])
        mock_instance.aquery = AsyncMock(side_effect=RuntimeError("gpu oom"))
        tokens = []
        with patch.object(svc, "_get_instance", new_callable=AsyncMock, return_value=mock_instance):
            async for tok in svc.stream("q", user_id=1):
                tokens.append(tok)
        assert any("error" in t.lower() for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_shared_ids_appends_synthesis(self):
        """
        288->286: `if not shared_ids` is False (shared_ids non-empty) so
        execution continues into the for-loop that queries shared vaults.
        291->exit: `yield synthesis` is reached and then the generator ends.
        """
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod

        svc = GraphRAGService()

        # Primary instance (user 1) — no astream_query, returns single token
        mock_primary = MagicMock(spec=[])
        mock_primary.aquery = AsyncMock(return_value="primary answer")

        # _query_single for shared user (user 2) — mock _get_instance for uid=2
        mock_shared = MagicMock(spec=[])
        mock_shared.aquery = AsyncMock(return_value="shared answer")

        async def _fake_get_instance(uid):
            return mock_primary if uid == 1 else mock_shared

        # Make _synthesise return a simple string without hitting real LLM
        real_singleton = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = False  # triggers the join fallback in _synthesise
        llm_mod.llm_provider = mock_llm

        tokens = []
        try:
            with patch.object(svc, "_get_instance", side_effect=_fake_get_instance):
                async for tok in svc.stream("q", user_id=1, owner_ids={1, 2}):
                    tokens.append(tok)
        finally:
            llm_mod.llm_provider = real_singleton

        # primary answer + separator + synthesis
        assert "primary answer" in tokens
        assert any("shared" in t or "---" in t or "context" in t for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_exception_via_astream_query(self):
        """astream_query raises -> except block -> yield error."""
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
        mock_instance = MagicMock(spec=[])

        async def _bad_stream(*a, **kw):
            raise RuntimeError("stream fail")
            yield  # pragma: no cover

        mock_instance.astream_query = _bad_stream
        tokens = []
        with patch.object(svc, "_get_instance", new_callable=AsyncMock, return_value=mock_instance):
            async for tok in svc.stream("q", user_id=1):
                tokens.append(tok)
        assert any("error" in t.lower() or "fail" in t.lower() for t in tokens)


# ===========================================================================
# llm_provider.py  lines 112, 114, 125, 181->179
# ===========================================================================

class TestLLMProviderActiveModel:

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

    @pytest.mark.asyncio
    async def test_initialize_ollama_non_200_skips(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_resp)
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
    """
    181->179: the `continue` arc that loops from the except clause back to
    the `for provider in providers` statement at line ~179.  Requires at
    least two providers so the loop actually iterates more than once, OR
    one provider that fails so `continue` is hit and execution reaches the
    final `raise` after the loop.
    """

    @pytest.mark.asyncio
    async def test_stream_all_providers_fail_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["ollama"]
        p._ollama_model = "llama3.2"
        mock_create = AsyncMock(side_effect=RuntimeError("connection refused"))
        mock_completions = MagicMock()
        mock_completions.create = mock_create
        mock_chat = MagicMock()
        mock_chat.completions = mock_completions
        mock_client = MagicMock()
        mock_client.chat = mock_chat
        p._ollama_client = mock_client
        with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
            async for _ in p.stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_stream_first_fails_second_succeeds_hits_continue_arc(self):
        """
        181->179: ollama fails (continue) -> loop back to 179 -> groq succeeds.
        This is the arc that makes the loop-back branch visible to coverage.
        """
        from gnosis.services.llm_provider import LLMProvider

        p = LLMProvider()
        p._available = ["ollama", "groq"]
        p._ollama_model = "llama3.2"

        # ollama client: create raises
        bad_create = AsyncMock(side_effect=RuntimeError("ollama down"))
        bad_completions = MagicMock()
        bad_completions.create = bad_create
        bad_chat = MagicMock()
        bad_chat.completions = bad_completions
        bad_client = MagicMock()
        bad_client.chat = bad_chat
        p._ollama_client = bad_client

        # groq client: create returns an async iterable of chunks
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content="hello"))]

        async def _good_stream(**kwargs):
            yield chunk

        good_create = AsyncMock(return_value=_good_stream())
        good_completions = MagicMock()
        good_completions.create = good_create
        good_chat = MagicMock()
        good_chat.completions = good_completions
        good_client = MagicMock()
        good_client.chat = good_chat
        p._groq_client = good_client

        tokens = []
        async for tok in p.stream("hello"):
            tokens.append(tok)

        assert "hello" in tokens


# ===========================================================================
# vault_sync.py
# ===========================================================================

class TestVaultSyncRunFullSync:
    """
    152->156: False branch of `if not vault_root.exists()` — vault exists,
              so execution falls through to md_files line.
              We must patch _get_vault_path (not get_settings) to avoid the
              module-level _VAULT_PATH cache returning a stale value.
    168->163: `except Exception` continue arc — _sync_file raises, except
              body yields an error line, then `continue` loops back to 163.
    """

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
    async def test_run_full_sync_vault_exists_falls_through(self, tmp_path):
        """152->156: vault exists — execution reaches md_files line."""
        from gnosis.services.vault_sync import run_full_sync_for_user
        mock_session = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        lines = []
        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync._resolve_owner_id",
                       new=AsyncMock(return_value=1)):
                with patch("gnosis.services.vault_sync.AsyncSessionFactory",
                           return_value=mock_cm):
                    async for line in run_full_sync_for_user(1):
                        lines.append(line)
        # Empty vault: should yield total:0 then done:
        assert any("total" in l for l in lines)
        assert any("done" in l for l in lines)

    @pytest.mark.asyncio
    async def test_run_full_sync_file_exception_yields_error_line(self, tmp_path):
        """168->163: _sync_file raises -> error line yielded -> continue arc."""
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
    """Lines 254-259: _handle_upsert except block."""

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
                await handler._handle_upsert(test_path)  # must not raise


class TestStartVaultWatcherException:
    """Lines 311-312: startup-sync except block."""

    @pytest.mark.asyncio
    async def test_start_vault_watcher_sync_exception_logged(self, tmp_path):
        from gnosis.services.vault_sync import start_vault_watcher
        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()

        async def _bad_sync(owner_id):
            raise RuntimeError("sync boom")
            yield  # pragma: no cover

        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync.run_full_sync_for_user",
                       side_effect=RuntimeError("sync boom")):
                with patch("gnosis.services.vault_sync.Observer", return_value=mock_observer):
                    observer = await start_vault_watcher(owner_id=1)
        assert observer is mock_observer


# ===========================================================================
# vector_store.py  line 156->158
# ===========================================================================

class TestVectorStoreClientCache:

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
