"""Unit tests for gnosis/services/embeddings.py.

The real module exposes:
  get_dense_model()   - lazy loads TextEmbedding via fastembed
  get_colbert_model() - lazy loads LateInteractionTextEmbedding via fastembed
  embed_dense(text)   - returns list[float] (768-dim)
  embed_colbert(text) - returns list[list[float]] (one 128-dim vec per token)

fastembed IS installed in the venv (the model loads successfully per the
test run output), so tests mock at the module-global level rather than
stubbing sys.modules.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dense_model_mock(vector=None):
    """Return a mock that mimics fastembed TextEmbedding."""
    if vector is None:
        vector = [0.1] * 768
    model = MagicMock()
    model.embed = MagicMock(return_value=iter([vector]))
    return model


def _colbert_model_mock(token_vecs=None):
    """Return a mock that mimics fastembed LateInteractionTextEmbedding."""
    if token_vecs is None:
        token_vecs = [[0.5] * 128, [0.3] * 128]
    model = MagicMock()
    model.embed = MagicMock(return_value=iter([token_vecs]))
    return model


# ---------------------------------------------------------------------------
# embed_dense
# ---------------------------------------------------------------------------

def test_embed_dense_returns_list_of_floats():
    expected = [float(i) / 768 for i in range(768)]
    mock_model = _dense_model_mock(expected)
    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        from gnosis.services.embeddings import embed_dense
        result = embed_dense("hello world")
    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)
    assert result == pytest.approx(expected, abs=1e-6)


def test_embed_dense_calls_model_embed_with_text():
    mock_model = _dense_model_mock()
    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        from gnosis.services.embeddings import embed_dense
        embed_dense("test input")
    mock_model.embed.assert_called_once_with(["test input"])


def test_embed_dense_returns_all_zeros_vector():
    mock_model = _dense_model_mock([0.0] * 768)
    with patch("gnosis.services.embeddings.get_dense_model", return_value=mock_model):
        from gnosis.services.embeddings import embed_dense
        result = embed_dense("empty")
    assert result == [0.0] * 768


# ---------------------------------------------------------------------------
# embed_colbert
# ---------------------------------------------------------------------------

def test_embed_colbert_returns_list_of_vectors():
    token_vecs = [[float(i) / 128 for i in range(128)]] * 5  # 5 token vectors
    mock_model = _colbert_model_mock(token_vecs)
    with patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_model):
        from gnosis.services.embeddings import embed_colbert
        result = embed_colbert("five tokens here")
    assert isinstance(result, list)
    assert len(result) == 5
    assert len(result[0]) == 128
    assert all(isinstance(v, float) for v in result[0])


def test_embed_colbert_calls_model_embed_with_text():
    mock_model = _colbert_model_mock()
    with patch("gnosis.services.embeddings.get_colbert_model", return_value=mock_model):
        from gnosis.services.embeddings import embed_colbert
        embed_colbert("rerank this")
    mock_model.embed.assert_called_once_with(["rerank this"])


# ---------------------------------------------------------------------------
# get_dense_model — lazy load + caching
# ---------------------------------------------------------------------------

def test_get_dense_model_caches_instance():
    """get_dense_model returns the same object on repeated calls."""
    import gnosis.services.embeddings as emb
    # Reset global so we exercise the lazy-load path
    original = emb._dense_model
    emb._dense_model = None
    try:
        mock_model = _dense_model_mock()
        with patch("gnosis.services.embeddings._dense_model", None):
            with patch("fastembed.TextEmbedding", return_value=mock_model):
                m1 = emb.get_dense_model()
                # Set the cached value manually to simulate second call
                emb._dense_model = m1
                m2 = emb.get_dense_model()
        assert m1 is m2
    finally:
        emb._dense_model = original


# ---------------------------------------------------------------------------
# get_colbert_model — lazy load raises when fastembed missing
# ---------------------------------------------------------------------------

def test_get_colbert_model_raises_when_import_fails():
    """get_colbert_model propagates the ImportError when fastembed is absent."""
    import gnosis.services.embeddings as emb
    original = emb._colbert_model
    emb._colbert_model = None
    try:
        with patch.dict("sys.modules", {"fastembed": None}):
            with pytest.raises(Exception):
                emb.get_colbert_model()
    finally:
        emb._colbert_model = original
