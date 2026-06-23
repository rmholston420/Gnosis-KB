"""Tests for gnosis/services/embeddings.py.

Real API:
  embed_dense(text: str) -> list[float]  (768-dim, uses fastembed TextEmbedding)
  embed_colbert(text: str) -> list[list[float]]  (128-dim multivec)
  get_dense_model() -> TextEmbedding  (lazy-loaded singleton)
  get_colbert_model() -> LateInteractionTextEmbedding  (lazy-loaded singleton)

All fastembed model loading is mocked via patch on the module-level getters.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# embed_dense
# ---------------------------------------------------------------------------

def test_embed_dense_returns_list_of_floats():
    from gnosis.services.embeddings import embed_dense

    mock_model = MagicMock()
    mock_model.embed.return_value = [[0.1, 0.2, 0.3] + [0.0] * 765]  # 768-dim

    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        result = embed_dense("hello world")

    assert isinstance(result, list)
    assert all(isinstance(x, float) for x in result)
    assert len(result) == 768


def test_embed_dense_calls_model_embed_with_list():
    from gnosis.services.embeddings import embed_dense

    mock_model = MagicMock()
    mock_model.embed.return_value = [[float(i) for i in range(768)]]

    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        embed_dense("test input")

    mock_model.embed.assert_called_once_with(["test input"])


def test_embed_dense_values_are_floats():
    from gnosis.services.embeddings import embed_dense

    mock_model = MagicMock()
    mock_model.embed.return_value = [[i * 0.001 for i in range(768)]]

    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        result = embed_dense("check types")

    assert result[0] == 0.0
    assert result[1] == 0.001


# ---------------------------------------------------------------------------
# embed_colbert
# ---------------------------------------------------------------------------

def test_embed_colbert_returns_list_of_lists():
    from gnosis.services.embeddings import embed_colbert

    # 5 tokens x 128-dim
    mock_tokens = [[float(i % 128) for i in range(128)] for _ in range(5)]
    mock_model = MagicMock()
    mock_model.embed.return_value = [mock_tokens]

    with patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_model):
        result = embed_colbert("hello world")

    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert len(result[0]) == 128
    assert all(isinstance(x, float) for x in result[0])


def test_embed_colbert_calls_model_embed():
    from gnosis.services.embeddings import embed_colbert

    mock_model = MagicMock()
    mock_model.embed.return_value = [[[0.1] * 128]]

    with patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_model):
        embed_colbert("text")

    mock_model.embed.assert_called_once_with(["text"])


# ---------------------------------------------------------------------------
# get_dense_model — lazy loading and caching
# ---------------------------------------------------------------------------

def test_get_dense_model_caches_instance():
    """Calling get_dense_model() twice returns the same object."""
    import gnosis.services.embeddings as emb

    mock_model = MagicMock()
    fake_fastembed = MagicMock()
    fake_fastembed.TextEmbedding.return_value = mock_model

    orig = emb._dense_model
    emb._dense_model = None
    try:
        with patch.dict("sys.modules", {"fastembed": fake_fastembed}):
            m1 = emb.get_dense_model()
            m2 = emb.get_dense_model()
        assert m1 is m2
    finally:
        emb._dense_model = orig


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------

def test_embeddings_module_exports_expected_names():
    import gnosis.services.embeddings as emb
    assert callable(emb.embed_dense)
    assert callable(emb.embed_colbert)
    assert callable(emb.get_dense_model)
    assert callable(emb.get_colbert_model)
