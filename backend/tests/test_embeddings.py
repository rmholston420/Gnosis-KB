"""Tests for gnosis/services/embeddings.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# get_embedding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_embedding_openai_returns_list():
    """Happy path: OpenAI provider returns a float list."""
    from gnosis.services.embeddings import get_embedding

    fake_embed_data = MagicMock()
    fake_embed_data.embedding = [0.1, 0.2, 0.3]
    fake_response = MagicMock()
    fake_response.data = [fake_embed_data]

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=fake_response)

    fake_openai = MagicMock()
    fake_openai.AsyncOpenAI.return_value = fake_client

    with patch.dict("sys.modules", {"openai": fake_openai}), \
         patch("gnosis.services.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "openai"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.embedding_model = "text-embedding-3-small"
        result = await get_embedding("hello world")

    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_get_embedding_local_returns_list():
    """Local/sentence-transformers provider path."""
    from gnosis.services.embeddings import get_embedding

    fake_model = MagicMock()
    fake_model.encode.return_value = [0.4, 0.5, 0.6]

    fake_st = MagicMock()
    fake_st.SentenceTransformer.return_value = fake_model

    with patch.dict("sys.modules", {"sentence_transformers": fake_st}), \
         patch("gnosis.services.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "local"
        mock_settings.local_embedding_model = "all-MiniLM-L6-v2"
        result = await get_embedding("hello")

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_embedding_unsupported_provider_raises():
    from gnosis.services.embeddings import get_embedding

    with patch("gnosis.services.embeddings.settings") as mock_settings:
        mock_settings.embedding_provider = "unknown_provider"
        with pytest.raises(Exception):
            await get_embedding("hello")


# ---------------------------------------------------------------------------
# embed_texts batch helper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_texts_returns_list_of_lists():
    from gnosis.services.embeddings import embed_texts

    with patch("gnosis.services.embeddings.get_embedding", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [0.1, 0.2]
        result = await embed_texts(["a", "b", "c"])

    assert len(result) == 3
    assert all(isinstance(r, list) for r in result)


@pytest.mark.asyncio
async def test_embed_texts_empty_input():
    from gnosis.services.embeddings import embed_texts
    result = await embed_texts([])
    assert result == []
