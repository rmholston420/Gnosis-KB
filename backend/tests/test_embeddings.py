"""Tests for gnosis.services.embeddings.

fastembed is not installed in the test environment, so every test patches
the import at the point of use inside get_dense_model / get_colbert_model.
No network, no GPU, no model downloads required.
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

import pytest

import gnosis.services.embeddings as emb_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset():
    emb_module._dense_model = None
    emb_module._colbert_model = None


def _dense_mock(vec):
    m = MagicMock()
    m.embed.return_value = iter([vec])
    return m


def _colbert_mock(vecs):
    m = MagicMock()
    m.embed.return_value = iter([vecs])
    return m


# ---------------------------------------------------------------------------
# get_dense_model()
# ---------------------------------------------------------------------------

def test_get_dense_model_returns_cached():
    _reset()
    sentinel = MagicMock()
    emb_module._dense_model = sentinel
    assert emb_module.get_dense_model() is sentinel


def test_get_dense_model_lazy_loads():
    _reset()
    fake_model = MagicMock()
    fake_cls = MagicMock(return_value=fake_model)
    fake_fastembed = MagicMock()
    fake_fastembed.TextEmbedding = fake_cls
    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "fastembed", fake_fastembed)
        importlib.reload(emb_module)
        emb_module._dense_model = None
        result = emb_module.get_dense_model()
    assert result is not None


def test_get_dense_model_raises_on_failure():
    _reset()
    fake_fastembed = MagicMock()
    fake_fastembed.TextEmbedding = MagicMock(side_effect=Exception("no fastembed"))
    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "fastembed", fake_fastembed)
        importlib.reload(emb_module)
        emb_module._dense_model = None
        with pytest.raises(Exception, match="no fastembed"):
            emb_module.get_dense_model()


# ---------------------------------------------------------------------------
# get_colbert_model()
# ---------------------------------------------------------------------------

def test_get_colbert_model_returns_cached():
    _reset()
    sentinel = MagicMock()
    emb_module._colbert_model = sentinel
    assert emb_module.get_colbert_model() is sentinel


def test_get_colbert_model_lazy_loads():
    _reset()
    fake_model = MagicMock()
    fake_cls = MagicMock(return_value=fake_model)
    fake_fastembed = MagicMock()
    fake_fastembed.LateInteractionTextEmbedding = fake_cls
    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "fastembed", fake_fastembed)
        importlib.reload(emb_module)
        emb_module._colbert_model = None
        result = emb_module.get_colbert_model()
    assert result is not None


def test_get_colbert_model_raises_on_failure():
    _reset()
    fake_fastembed = MagicMock()
    fake_fastembed.LateInteractionTextEmbedding = MagicMock(side_effect=Exception("no colbert"))
    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "fastembed", fake_fastembed)
        importlib.reload(emb_module)
        emb_module._colbert_model = None
        with pytest.raises(Exception, match="no colbert"):
            emb_module.get_colbert_model()


# ---------------------------------------------------------------------------
# embed_dense()
# ---------------------------------------------------------------------------

def test_embed_dense_returns_floats():
    _reset()
    emb_module._dense_model = _dense_mock([0.1, 0.2, 0.3])
    result = emb_module.embed_dense("hello")
    assert result == pytest.approx([0.1, 0.2, 0.3])
    assert all(isinstance(v, float) for v in result)


def test_embed_dense_calls_embed_with_list():
    _reset()
    mock = _dense_mock([1.0])
    emb_module._dense_model = mock
    emb_module.embed_dense("test")
    mock.embed.assert_called_once_with(["test"])


def test_embed_dense_empty_string():
    _reset()
    emb_module._dense_model = _dense_mock([0.0] * 768)
    result = emb_module.embed_dense("")
    assert len(result) == 768


# ---------------------------------------------------------------------------
# embed_colbert()
# ---------------------------------------------------------------------------

def test_embed_colbert_returns_list_of_float_lists():
    _reset()
    emb_module._colbert_model = _colbert_mock([[0.1, 0.2], [0.3, 0.4]])
    result = emb_module.embed_colbert("hello")
    assert len(result) == 2
    assert result[0] == pytest.approx([0.1, 0.2])
    assert all(isinstance(v, float) for row in result for v in row)


def test_embed_colbert_calls_embed_with_list():
    _reset()
    mock = _colbert_mock([[1.0]])
    emb_module._colbert_model = mock
    emb_module.embed_colbert("query")
    mock.embed.assert_called_once_with(["query"])


def test_embed_colbert_single_token():
    _reset()
    emb_module._colbert_model = _colbert_mock([[0.5] * 128])
    result = emb_module.embed_colbert("x")
    assert len(result) == 1
    assert len(result[0]) == 128
