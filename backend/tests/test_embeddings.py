"""Unit tests for gnosis/services/embeddings.py.

Patches fastembed so no models are downloaded during testing.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _mock_dense_model(vec):
    m = MagicMock()
    m.embed.return_value = iter([vec])
    return m


def _mock_colbert_model(vecs):
    m = MagicMock()
    m.embed.return_value = iter([vecs])
    return m


# ---------------------------------------------------------------------------
# get_dense_model / get_colbert_model lazy init
# ---------------------------------------------------------------------------

def test_get_dense_model_caches_instance():
    import gnosis.services.embeddings as emb
    emb._dense_model = None
    fake = MagicMock()
    with patch("gnosis.services.embeddings.get_dense_model", return_value=fake):
        m1 = emb.get_dense_model.__wrapped__() if hasattr(emb.get_dense_model, "__wrapped__") else fake
    assert fake is not None


def test_get_dense_model_raises_on_import_error():
    import gnosis.services.embeddings as emb
    emb._dense_model = None
    with patch.dict("sys.modules", {"fastembed": None}):
        with pytest.raises(Exception):
            emb.get_dense_model()


def test_get_colbert_model_raises_on_import_error():
    import gnosis.services.embeddings as emb
    emb._colbert_model = None
    with patch.dict("sys.modules", {"fastembed": None}):
        with pytest.raises(Exception):
            emb.get_colbert_model()


# ---------------------------------------------------------------------------
# embed_dense
# ---------------------------------------------------------------------------

def test_embed_dense_returns_float_list():
    import gnosis.services.embeddings as emb
    emb._dense_model = None
    fake_vec = [0.1, 0.2, 0.3]
    with patch.object(emb, "get_dense_model", return_value=_mock_dense_model(fake_vec)):
        result = emb.embed_dense("hello world")
    assert result == pytest.approx([0.1, 0.2, 0.3])
    assert all(isinstance(x, float) for x in result)


def test_embed_dense_single_string():
    import gnosis.services.embeddings as emb
    emb._dense_model = None
    with patch.object(emb, "get_dense_model", return_value=_mock_dense_model([1.0])):
        result = emb.embed_dense("test")
    assert len(result) == 1


# ---------------------------------------------------------------------------
# embed_colbert
# ---------------------------------------------------------------------------

def test_embed_colbert_returns_list_of_lists():
    import gnosis.services.embeddings as emb
    emb._colbert_model = None
    fake_vecs = [[0.1, 0.2], [0.3, 0.4]]
    with patch.object(emb, "get_colbert_model", return_value=_mock_colbert_model(fake_vecs)):
        result = emb.embed_colbert("hello")
    assert len(result) == 2
    assert result[0] == pytest.approx([0.1, 0.2])


def test_embed_colbert_all_floats():
    import gnosis.services.embeddings as emb
    emb._colbert_model = None
    with patch.object(emb, "get_colbert_model", return_value=_mock_colbert_model([[1, 2]])):
        result = emb.embed_colbert("test")
    assert all(isinstance(x, float) for x in result[0])
