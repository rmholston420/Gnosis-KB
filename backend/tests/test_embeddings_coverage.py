"""Gap-filling tests for gnosis/services/embeddings.py.

Covers lazy-load logic, error propagation, and the embed_dense / embed_colbert
public API.  fastembed is never actually loaded — we mock the import.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import gnosis.services.embeddings as emb_mod


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset module-level singletons before each test."""
    emb_mod._dense_model = None
    emb_mod._colbert_model = None
    yield
    emb_mod._dense_model = None
    emb_mod._colbert_model = None


# ---------------------------------------------------------------------------
# get_dense_model
# ---------------------------------------------------------------------------


def test_get_dense_model_lazy_loads():
    mock_model = MagicMock()
    mock_te_class = MagicMock(return_value=mock_model)
    with patch.dict("sys.modules", {"fastembed": MagicMock(TextEmbedding=mock_te_class)}):
        result = emb_mod.get_dense_model()
    assert result is mock_model
    mock_te_class.assert_called_once_with(model_name="BAAI/bge-base-en-v1.5")


def test_get_dense_model_returns_cached():
    sentinel = object()
    emb_mod._dense_model = sentinel
    result = emb_mod.get_dense_model()
    assert result is sentinel


def test_get_dense_model_raises_on_import_error():
    with patch("builtins.__import__", side_effect=ImportError("no fastembed")):
        # Reset so the lazy-load branch is entered
        emb_mod._dense_model = None
        with pytest.raises(Exception):
            emb_mod.get_dense_model()


# ---------------------------------------------------------------------------
# get_colbert_model
# ---------------------------------------------------------------------------


def test_get_colbert_model_lazy_loads():
    mock_model = MagicMock()
    mock_class = MagicMock(return_value=mock_model)
    with patch.dict(
        "sys.modules",
        {"fastembed": MagicMock(LateInteractionTextEmbedding=mock_class)},
    ):
        result = emb_mod.get_colbert_model()
    assert result is mock_model
    mock_class.assert_called_once_with(model_name="colbert-ir/colbertv2.0")


def test_get_colbert_model_returns_cached():
    sentinel = object()
    emb_mod._colbert_model = sentinel
    assert emb_mod.get_colbert_model() is sentinel


# ---------------------------------------------------------------------------
# embed_dense
# ---------------------------------------------------------------------------


def test_embed_dense_returns_float_list():
    mock_model = MagicMock()
    mock_model.embed.return_value = [[0.1, 0.2, 0.3]]
    emb_mod._dense_model = mock_model

    result = emb_mod.embed_dense("hello world")

    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)
    assert result == [0.1, 0.2, 0.3]
    mock_model.embed.assert_called_once_with(["hello world"])


def test_embed_dense_propagates_model_error():
    mock_model = MagicMock()
    mock_model.embed.side_effect = RuntimeError("GPU OOM")
    emb_mod._dense_model = mock_model

    with pytest.raises(RuntimeError, match="GPU OOM"):
        emb_mod.embed_dense("text")


# ---------------------------------------------------------------------------
# embed_colbert
# ---------------------------------------------------------------------------


def test_embed_colbert_returns_list_of_float_lists():
    mock_model = MagicMock()
    mock_model.embed.return_value = [[[0.5, 0.6], [0.7, 0.8]]]
    emb_mod._colbert_model = mock_model

    result = emb_mod.embed_colbert("hello")

    assert isinstance(result, list)
    assert result == [[0.5, 0.6], [0.7, 0.8]]
    mock_model.embed.assert_called_once_with(["hello"])


def test_embed_colbert_propagates_model_error():
    mock_model = MagicMock()
    mock_model.embed.side_effect = ValueError("bad input")
    emb_mod._colbert_model = mock_model

    with pytest.raises(ValueError, match="bad input"):
        emb_mod.embed_colbert("text")
