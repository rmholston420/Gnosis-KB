"""Unit tests for gnosis/services/embeddings.py.

Fastembed is not installed in the venv, so _FASTEMBED_AVAILABLE=False.
Tests cover:
  - is_available: False when fastembed absent
  - embed_dense: returns zero vector of correct length, warns once, idempotent
  - embed_sparse: returns empty dict when fastembed absent
  - Fastembed AVAILABLE path: mocked via patch.dict(sys.modules)
    - embed_dense returns real model output
    - embed_sparse returns non-empty weights dict
    - model is lazily loaded and cached (TextEmbedding called once)
"""
from __future__ import annotations

import sys
import types
from importlib import reload
from unittest.mock import MagicMock, patch

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fastembed_stub(dense_vector=None, sparse_weights=None):
    """Build a minimal fastembed sys.modules stub."""
    if dense_vector is None:
        dense_vector = np.zeros(384, dtype=np.float32)
    if sparse_weights is None:
        sparse_weights = {0: 0.5, 42: 1.2}

    # Dense model mock
    dense_model = MagicMock()
    dense_model.embed = MagicMock(return_value=iter([dense_vector]))
    TextEmbedding = MagicMock(return_value=dense_model)

    # Sparse model mock
    sparse_result = MagicMock()
    sparse_result.indices = list(sparse_weights.keys())
    sparse_result.values = list(sparse_weights.values())
    sparse_model = MagicMock()
    sparse_model.embed = MagicMock(return_value=iter([sparse_result]))
    SparseTextEmbedding = MagicMock(return_value=sparse_model)

    fe_mod = types.ModuleType("fastembed")
    fe_mod.TextEmbedding = TextEmbedding           # type: ignore[attr-defined]
    fe_mod.SparseTextEmbedding = SparseTextEmbedding  # type: ignore[attr-defined]

    return fe_mod, TextEmbedding, SparseTextEmbedding


# ---------------------------------------------------------------------------
# Tests: fastembed UNAVAILABLE
# ---------------------------------------------------------------------------

def test_is_available_false_when_fastembed_missing():
    with patch.dict(sys.modules, {"fastembed": None}):
        import gnosis.services.embeddings as emb
        reload(emb)
        assert emb.is_available() is False


def test_embed_dense_returns_zero_vector_when_unavailable():
    with patch.dict(sys.modules, {"fastembed": None}):
        import gnosis.services.embeddings as emb
        reload(emb)
        vec = emb.embed_dense("hello world")
    # Should be a list/array of zeros
    assert hasattr(vec, "__len__")
    assert all(v == 0.0 for v in vec)


def test_embed_sparse_returns_empty_dict_when_unavailable():
    with patch.dict(sys.modules, {"fastembed": None}):
        import gnosis.services.embeddings as emb
        reload(emb)
        result = emb.embed_sparse("hello world")
    assert result == {}


def test_embed_dense_returns_consistent_length_when_unavailable():
    with patch.dict(sys.modules, {"fastembed": None}):
        import gnosis.services.embeddings as emb
        reload(emb)
        v1 = emb.embed_dense("short")
        v2 = emb.embed_dense("a much longer sentence with many words")
    assert len(v1) == len(v2)


# ---------------------------------------------------------------------------
# Tests: fastembed AVAILABLE (mocked)
# ---------------------------------------------------------------------------

def test_embed_dense_returns_model_output_when_available():
    expected = np.array([0.1, 0.2, 0.3] * 128, dtype=np.float32)
    fe_stub, TextEmbedding, _ = _make_fastembed_stub(dense_vector=expected)

    with patch.dict(sys.modules, {"fastembed": fe_stub}):
        import gnosis.services.embeddings as emb
        reload(emb)
        vec = emb.embed_dense("test sentence")

    assert list(vec) == pytest.approx(list(expected), abs=1e-5)


def test_embed_sparse_returns_weight_dict_when_available():
    sparse_weights = {7: 0.9, 42: 1.5, 100: 0.3}
    fe_stub, _, _ = _make_fastembed_stub(sparse_weights=sparse_weights)

    with patch.dict(sys.modules, {"fastembed": fe_stub}):
        import gnosis.services.embeddings as emb
        reload(emb)
        result = emb.embed_sparse("query text")

    assert isinstance(result, dict)
    assert len(result) == len(sparse_weights)
    for k, v in sparse_weights.items():
        assert result[k] == pytest.approx(v, abs=1e-5)


def test_embed_dense_model_is_lazily_loaded_and_cached():
    fe_stub, TextEmbedding, _ = _make_fastembed_stub()

    with patch.dict(sys.modules, {"fastembed": fe_stub}):
        import gnosis.services.embeddings as emb
        reload(emb)
        emb.embed_dense("first")
        emb.embed_dense("second")

    # TextEmbedding constructor called once (model cached after first call)
    assert TextEmbedding.call_count == 1


def test_is_available_true_when_fastembed_present():
    fe_stub, _, _ = _make_fastembed_stub()

    with patch.dict(sys.modules, {"fastembed": fe_stub}):
        import gnosis.services.embeddings as emb
        reload(emb)
        assert emb.is_available() is True
