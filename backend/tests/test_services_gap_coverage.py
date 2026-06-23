"""
Definitive gap coverage.

graph_rag.py stream() arcs
--------------------------
288->286 : `if answer and not answer.startswith(...)` False branch.
           The shared vault returns an unavailability string so it is
           filtered out; shared_answers stays empty; `if shared_answers:`
           is False; generator ends without yielding synthesis.
           This arc is 288->286 because `if answer ...` is False so
           execution skips the append and loops back to `for uid` at 286.

291->exit: `if shared_answers:` True -> yield separator -> yield synthesis
           -> generator falls off the end.
           Need shared vault returning a GOOD answer so shared_answers is
           non-empty and both yield statements at 292-294 execute.

The existing test_stream_shared_ids_appends_synthesis already hits 291->exit
but may not hit 288->286.  We add a dedicated test for the filter-out case.
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
    def test_lightrag_unavailable_flag_set_false(self):
        saved = {k: v for k, v in sys.modules.items() if "lightrag" in k}
        for k in list(saved):
            sys.modules.pop(k, None)
        gr_saved = sys.modules.pop("gnosis.services.graph_rag", None)
        try:
            sys.modules["lightrag"] = None  # type: ignore[assignment]
            import gnosis.services.graph_rag as gr_fresh
            importlib.reload(gr_fresh)
            assert gr_fresh._LIGHTRAG_AVAILABLE is False
        finally:
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
# graph_rag.py  line 187  (query: exactly-one answer path)
# ===========================================================================

class TestGraphRAGQuerySingleAnswer:
    @pytest.mark.asyncio
    async def test_query_one_valid_answer_strips_vault_header(self):
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()

        async def _fake_query_single(uid, question, mode):
            if uid == 1:
                return "real answer from vault 1"
            return "Graph-RAG is unavailable (LightRAG not initialised). Ensure Ollama is running and lightrag-hku is installed."

        with patch.object(svc, "_query_single", side_effect=_fake_query_single):
            result = await svc.query("q?", user_id=1, owner_ids={1, 2})

        assert "real answer from vault 1" in result
        assert "[Vault" not in result

    @pytest.mark.asyncio
    async def test_query_no_valid_answers_returns_unavailable(self):
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()

        async def _fake_query_single(uid, question, mode):
            return "Graph-RAG is unavailable (LightRAG not initialised). Ensure Ollama is running and lightrag-hku is installed."

        with patch.object(svc, "_query_single", side_effect=_fake_query_single):
            result = await svc.query("q?", user_id=1, owner_ids={1, 2})

        assert "unavailable" in result.lower()


# ===========================================================================
# graph_rag.py  _synthesise helpers
# ===========================================================================

class TestGraphRAGSynthesise:
    @pytest.mark.asyncio
    async def test_synthesise_llm_unavailable_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod
        svc = GraphRAGService()
        answers = ["[Vault 1]\nanswer one", "[Vault 2]\nanswer two"]
        real = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = False
        llm_mod.llm_provider = mock_llm
        try:
            result = await svc._synthesise("q", answers)
        finally:
            llm_mod.llm_provider = real
        assert "answer one" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_synthesise_llm_raises_returns_joined(self):
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod
        svc = GraphRAGService()
        answers = ["[Vault 1]\nfoo", "[Vault 2]\nbar"]
        real = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = True
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
        llm_mod.llm_provider = mock_llm
        try:
            result = await svc._synthesise("q", answers)
        finally:
            llm_mod.llm_provider = real
        assert "foo" in result


# ===========================================================================
# graph_rag.py  stream() arcs
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
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()
        mock_instance = MagicMock(spec=[])
        mock_instance.aquery = AsyncMock(return_value="result text")
        tokens = []
        with patch.object(svc, "_get_instance", new_callable=AsyncMock, return_value=mock_instance):
            async for tok in svc.stream("q", user_id=1, owner_ids={1}):
                tokens.append(tok)
        assert tokens == ["result text"]

    @pytest.mark.asyncio
    async def test_stream_aquery_raises_yields_error(self):
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
    async def test_stream_shared_answer_filtered_out_288_286(self):
        """
        288->286: `if answer and not answer.startswith(...)` False branch.
        The shared vault (uid=2) returns an unavailability string, so the
        `if` condition is False, shared_answers stays empty, `if shared_answers:`
        is False, generator ends without yielding synthesis.
        """
        from gnosis.services.graph_rag import GraphRAGService
        svc = GraphRAGService()

        # Primary instance (uid=1): no astream_query, returns single token
        mock_primary = MagicMock(spec=[])
        mock_primary.aquery = AsyncMock(return_value="primary answer")

        # Shared instance (uid=2): returns unavailability string -> filtered out
        mock_shared = MagicMock(spec=[])
        mock_shared.aquery = AsyncMock(
            return_value="Graph-RAG is unavailable (LightRAG not initialised). "
                         "Ensure Ollama is running and lightrag-hku is installed."
        )

        async def _fake_get_instance(uid):
            return mock_primary if uid == 1 else mock_shared

        tokens = []
        with patch.object(svc, "_get_instance", side_effect=_fake_get_instance):
            async for tok in svc.stream("q", user_id=1, owner_ids={1, 2}):
                tokens.append(tok)

        # Primary answer yielded; no synthesis block appended
        assert "primary answer" in tokens
        assert not any("context from shared" in t for t in tokens)
        assert not any("---" in t for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_shared_ids_appends_synthesis_291_exit(self):
        """
        291->exit: `if shared_answers:` True -> yield separator -> yield synthesis
        -> generator falls off the end.
        Need shared vault to return a GOOD (non-filtered) answer.
        """
        from gnosis.services.graph_rag import GraphRAGService
        import gnosis.services.llm_provider as llm_mod
        svc = GraphRAGService()

        mock_primary = MagicMock(spec=[])
        mock_primary.aquery = AsyncMock(return_value="primary answer")
        mock_shared = MagicMock(spec=[])
        mock_shared.aquery = AsyncMock(return_value="shared vault answer")

        async def _fake_get_instance(uid):
            return mock_primary if uid == 1 else mock_shared

        real = llm_mod.llm_provider
        mock_llm = MagicMock()
        mock_llm.is_available = False  # _synthesise join fallback
        llm_mod.llm_provider = mock_llm
        tokens = []
        try:
            with patch.object(svc, "_get_instance", side_effect=_fake_get_instance):
                async for tok in svc.stream("q", user_id=1, owner_ids={1, 2}):
                    tokens.append(tok)
        finally:
            llm_mod.llm_provider = real

        assert "primary answer" in tokens
        assert any("shared vault answer" in t or "---" in t or "context" in t
                   for t in tokens)

    @pytest.mark.asyncio
    async def test_stream_exception_via_astream_query(self):
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
# llm_provider.py
# ===========================================================================

class TestLLMProviderGetClientAndModel:
    def test_get_client_and_model_groq(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["groq"]
        p._groq_client = MagicMock()
        client, model = p._get_client_and_model()
        assert client is p._groq_client
        assert model == "llama-3.3-70b-versatile"

    def test_get_client_and_model_openai(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["openai"]
        p._openai_client = MagicMock()
        client, model = p._get_client_and_model()
        assert client is p._openai_client
        assert model == "gpt-4o-mini"

    def test_get_client_and_model_none_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = []
        with pytest.raises(RuntimeError, match="No LLM provider available"):
            p._get_client_and_model()


class TestLLMProviderGetClientFor:
    def test_get_client_for_ollama_client_none_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["ollama"]
        p._ollama_client = None
        with pytest.raises(ValueError, match="Unknown or unconfigured provider"):
            p._get_client_for("ollama")

    def test_get_client_for_unknown_provider_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        with pytest.raises(ValueError, match="Unknown or unconfigured provider"):
            p._get_client_for("anthropic")


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


class TestLLMProviderSwapModel:
    def test_swap_model_no_ollama_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["groq"]
        with pytest.raises(RuntimeError, match="Ollama is not an available provider"):
            p.swap_model("llama3.2")


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
        mock_http_client.get = AsyncMock(side_effect=Exception("refused"))
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


class TestLLMProviderStream:
    @pytest.mark.asyncio
    async def test_stream_empty_delta_skips_yield(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["openai"]
        p._openai_client = MagicMock()
        chunk_empty = MagicMock()
        chunk_empty.choices = [MagicMock(delta=MagicMock(content=""))]
        chunk_real = MagicMock()
        chunk_real.choices = [MagicMock(delta=MagicMock(content="hello"))]

        async def _fake_stream(**kwargs):
            yield chunk_empty
            yield chunk_real

        p._openai_client.chat.completions.create = AsyncMock(return_value=_fake_stream())
        tokens = []
        async for tok in p.stream("q"):
            tokens.append(tok)
        assert tokens == ["hello"]

    @pytest.mark.asyncio
    async def test_stream_all_providers_fail_raises(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["ollama"]
        p._ollama_model = "llama3.2"
        p._ollama_client = MagicMock()
        p._ollama_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("down")
        )
        with pytest.raises(RuntimeError, match="All LLM stream providers failed"):
            async for _ in p.stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_stream_first_fails_second_succeeds(self):
        from gnosis.services.llm_provider import LLMProvider
        p = LLMProvider()
        p._available = ["ollama", "groq"]
        p._ollama_model = "llama3.2"
        p._ollama_client = MagicMock()
        p._ollama_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("ollama down")
        )
        p._groq_client = MagicMock()
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content="groq reply"))]

        async def _good(**kwargs):
            yield chunk

        p._groq_client.chat.completions.create = AsyncMock(return_value=_good())
        tokens = []
        async for tok in p.stream("hello"):
            tokens.append(tok)
        assert "groq reply" in tokens


# ===========================================================================
# vault_sync.py
# ===========================================================================

class TestVaultSyncTagExists:
    @pytest.mark.asyncio
    async def test_sync_file_existing_tag_skips_creation(self, tmp_path):
        from gnosis.services.vault_sync import _sync_file
        md = tmp_path / "note.md"
        md.write_text("---\ntitle: T\nid: t1\ntags:\n  - existingtag\n---\nBody.")
        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        existing_tag = MagicMock()
        existing_tag.name = "existingtag"
        note_result = MagicMock()
        note_result.scalar_one_or_none = MagicMock(return_value=None)
        tag_result = MagicMock()
        tag_result.scalar_one_or_none = MagicMock(return_value=existing_tag)
        notag_result = MagicMock()
        link_delete_result = MagicMock()
        notetag_insert_result = MagicMock()
        db.execute = AsyncMock(side_effect=[
            note_result,
            notag_result,
            tag_result,
            notetag_insert_result,
            link_delete_result,
        ])
        with patch("gnosis.services.vault_sync.get_settings",
                   return_value=MagicMock(vault_path=str(tmp_path))), \
             patch("gnosis.services.vault_sync.upsert_note"):
            line = await _sync_file(md, owner_id=1, db_session=db)
        assert line.startswith("synced:")


class TestVaultSyncWikilinkTargetNotFound:
    @pytest.mark.asyncio
    async def test_sync_file_wikilink_target_not_found(self, tmp_path):
        from gnosis.services.vault_sync import _sync_file
        md = tmp_path / "note.md"
        md.write_text("---\ntitle: Source\nid: src\n---\n[[Missing Note]]")
        db = AsyncMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        note_result = MagicMock()
        note_result.scalar_one_or_none = MagicMock(return_value=None)
        link_delete_result = MagicMock()
        target_result = MagicMock()
        target_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[
            note_result,
            link_delete_result,
            link_delete_result,
            target_result,
        ])
        with patch("gnosis.services.vault_sync.get_settings",
                   return_value=MagicMock(vault_path=str(tmp_path))), \
             patch("gnosis.services.vault_sync.upsert_note"):
            line = await _sync_file(md, owner_id=1, db_session=db)
        assert line.startswith("synced:")
        from gnosis.models.link import Link
        link_adds = [c for c in db.add.call_args_list
                     if isinstance(c.args[0], Link)]
        assert len(link_adds) == 0


class TestVaultSyncRunFullSync:
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

    @pytest.mark.asyncio
    async def test_run_full_sync_vault_exists_falls_through(self, tmp_path):
        from gnosis.services.vault_sync import run_full_sync_for_user
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        lines = []
        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync._resolve_owner_id",
                       new=AsyncMock(return_value=1)):
                with patch("gnosis.services.vault_sync.AsyncSessionFactory",
                           return_value=mock_cm):
                    async for line in run_full_sync_for_user(1):
                        lines.append(line)
        assert any("total" in l for l in lines)

    @pytest.mark.asyncio
    async def test_run_full_sync_file_exception_yields_error_line(self, tmp_path):
        from gnosis.services.vault_sync import run_full_sync_for_user
        (tmp_path / "note.md").write_text("---\ntitle: t\n---\nbody")
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
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


class TestVaultGetLoop:
    def test_get_loop_caches_on_second_call(self):
        from gnosis.services.vault_sync import VaultEventHandler
        handler = VaultEventHandler(owner_id=1)
        handler._loop = None
        loop1 = handler._get_loop()
        loop2 = handler._get_loop()
        assert loop1 is loop2

    def test_get_loop_fallback_new_event_loop(self):
        from gnosis.services.vault_sync import VaultEventHandler
        handler = VaultEventHandler(owner_id=1)
        handler._loop = None
        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            with patch("asyncio.new_event_loop", return_value=MagicMock()) as mock_new:
                loop = handler._get_loop()
        assert loop is mock_new.return_value


class TestVaultEventHandlerUpsert:
    @pytest.mark.asyncio
    async def test_handle_upsert_exception_is_swallowed(self, tmp_path):
        from gnosis.services.vault_sync import VaultEventHandler
        handler = VaultEventHandler(owner_id=1)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        with patch("gnosis.services.vault_sync.AsyncSessionFactory", return_value=mock_cm):
            with patch("gnosis.services.vault_sync._sync_file",
                       new=AsyncMock(side_effect=RuntimeError("db down"))):
                await handler._handle_upsert(tmp_path / "note.md")


class TestVaultHandleDeleteValueError:
    @pytest.mark.asyncio
    async def test_handle_delete_path_outside_vault(self, tmp_path):
        import tempfile
        from gnosis.services.vault_sync import VaultEventHandler
        handler = VaultEventHandler(owner_id=1)
        with tempfile.TemporaryDirectory() as other_dir:
            outside_path = Path(other_dir) / "ghost.md"
            outside_path.write_text("content")
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db = AsyncMock()
            mock_db.execute = AsyncMock(return_value=result)
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            with patch("gnosis.services.vault_sync._get_vault_path",
                       return_value=tmp_path):
                with patch("gnosis.services.vault_sync.AsyncSessionFactory",
                           return_value=mock_cm):
                    await handler._handle_delete(outside_path)


class TestStartVaultWatcherException:
    @pytest.mark.asyncio
    async def test_start_vault_watcher_sync_exception_logged(self, tmp_path):
        from gnosis.services.vault_sync import start_vault_watcher
        mock_observer = MagicMock()
        mock_observer.schedule = MagicMock()
        mock_observer.start = MagicMock()
        with patch("gnosis.services.vault_sync._get_vault_path", return_value=tmp_path):
            with patch("gnosis.services.vault_sync.run_full_sync_for_user",
                       side_effect=RuntimeError("sync boom")):
                with patch("gnosis.services.vault_sync.Observer", return_value=mock_observer):
                    observer = await start_vault_watcher(owner_id=1)
        assert observer is mock_observer


# ===========================================================================
# vector_store.py
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


class TestVectorStoreHybridSearchIncludeLegacy:
    def test_hybrid_search_include_legacy_false_skips_sentinel(self):
        import gnosis.services.vector_store as vs
        mock_client = MagicMock()
        mock_client.query_points.return_value = MagicMock(points=[])
        mock_settings = MagicMock()
        mock_settings.qdrant_collection_name = "gnosis"
        with patch("gnosis.services.vector_store.get_qdrant_client",
                   return_value=mock_client), \
             patch("gnosis.services.vector_store.get_settings",
                   return_value=mock_settings), \
             patch("gnosis.services.vector_store.embed_dense",
                   return_value=[0.1] * 768):
            result = vs.hybrid_search(
                "test query",
                owner_ids={1},
                include_legacy=False,
            )
        assert isinstance(result, list)
        assert mock_client.query_points.called

    def test_hybrid_search_include_legacy_true_appends_sentinel(self):
        import gnosis.services.vector_store as vs
        mock_client = MagicMock()
        mock_client.query_points.return_value = MagicMock(points=[])
        mock_settings = MagicMock()
        mock_settings.qdrant_collection_name = "gnosis"
        with patch("gnosis.services.vector_store.get_qdrant_client",
                   return_value=mock_client), \
             patch("gnosis.services.vector_store.get_settings",
                   return_value=mock_settings), \
             patch("gnosis.services.vector_store.embed_dense",
                   return_value=[0.1] * 768):
            result = vs.hybrid_search(
                "test query",
                owner_ids={1},
                include_legacy=True,
            )
        assert isinstance(result, list)
