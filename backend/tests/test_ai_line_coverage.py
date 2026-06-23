"""
Line-level coverage for gnosis/routers/ai.py.

Previously two tests failed because they patched a non-existent symbol.
All ingest_note tests now use the correct patch target:
    gnosis.routers.ai._lightrag_available
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


def _note(note_id="line-1", title="Line Note", body="body", owner_id=1):
    n = MagicMock()
    n.id = note_id
    n.title = title
    n.body = body
    n.owner_id = owner_id
    n.is_deleted = False
    return n


# ---------------------------------------------------------------------------
# _lightrag_available() — the function itself
# ---------------------------------------------------------------------------

def test_lightrag_available_check_returns_bool():
    """
    _lightrag_available() is a plain sync function.
    When lightrag is not installed it returns False; we verify the
    return type is bool regardless of the environment.
    """
    from gnosis.routers.ai import _lightrag_available
    result = _lightrag_available()
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# ingest_note — success path (graph_indexed=True)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_succeeds_and_marks_graph_indexed(
    async_client: AsyncClient, auth_headers: dict
):
    note = _note()

    mock_gr = MagicMock()
    mock_gr.__bool__ = MagicMock(return_value=True)
    mock_gr.ingest_note = AsyncMock(return_value=None)

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag", mock_gr),
        patch("gnosis.routers.ai.update", MagicMock()),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_indexed"] is True
    assert note.title in body["message"]


# ---------------------------------------------------------------------------
# ingest_note — unavailable (graph_indexed=False)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_returns_false_when_lightrag_unavailable(
    async_client: AsyncClient, auth_headers: dict
):
    note = _note(note_id="line-2", title="Line Note 2")

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=False),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["graph_indexed"] is False


# ---------------------------------------------------------------------------
# ingest_note — exception → 500
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ingest_note_exception_raises_500(
    async_client: AsyncClient, auth_headers: dict
):
    note = _note(note_id="line-3", title="Line Note 3")

    mock_gr = MagicMock()
    mock_gr.__bool__ = MagicMock(return_value=True)
    mock_gr.ingest_note = AsyncMock(side_effect=Exception("line-level failure"))

    with (
        patch("gnosis.routers.ai._get_note_or_404", AsyncMock(return_value=note)),
        patch("gnosis.routers.ai._lightrag_available", return_value=True),
        patch("gnosis.routers.ai.graph_rag", mock_gr),
    ):
        resp = await async_client.post(
            f"/api/v1/ai/ingest-note/{note.id}",
            headers=auth_headers,
        )

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# _parse_json_list — various inputs
# ---------------------------------------------------------------------------

def test_parse_json_list_valid_array():
    from gnosis.routers.ai import _parse_json_list
    result = _parse_json_list('["alpha", "beta", "gamma"]')
    assert result == ["alpha", "beta", "gamma"]


def test_parse_json_list_fallback_to_lines():
    from gnosis.routers.ai import _parse_json_list
    raw = "- first\n- second\n- third"
    result = _parse_json_list(raw)
    assert "first" in result


def test_parse_json_list_invalid_json_in_brackets():
    from gnosis.routers.ai import _parse_json_list
    raw = "[not valid json]"
    result = _parse_json_list(raw)
    # Falls back to line-by-line; should not raise
    assert isinstance(result, list)


def test_parse_json_list_non_list_json():
    from gnosis.routers.ai import _parse_json_list
    # JSON array containing non-strings gets cast to str
    result = _parse_json_list("[1, 2, 3]")
    assert result == ["1", "2", "3"]


# ---------------------------------------------------------------------------
# _build_rag_context
# ---------------------------------------------------------------------------

def test_build_rag_context_empty_hits():
    from gnosis.routers.ai import _build_rag_context
    assert _build_rag_context([]) == ""


def test_build_rag_context_with_hits():
    from gnosis.routers.ai import _build_rag_context
    hits = [
        {"title": "Note A", "text_snippet": "snippet A", "folder": "inbox"},
        {"title": "Note B", "text_snippet": "snippet B", "folder": "projects"},
    ]
    ctx = _build_rag_context(hits)
    assert "Note A" in ctx
    assert "Note B" in ctx
    assert "inbox" in ctx


# ---------------------------------------------------------------------------
# _build_moc_markdown
# ---------------------------------------------------------------------------

def test_build_moc_markdown_structure():
    from gnosis.routers.ai import _build_moc_markdown
    from gnosis.schemas.ai import MocSection
    sections = [
        MocSection(heading="Section One", summary="Summary.", wikilinks=["Note A", "Note B"]),
    ]
    md = _build_moc_markdown("philosophy", "MOC — Philosophy", sections)
    assert "MOC — Philosophy" in md
    assert "Section One" in md
    assert "[[Note A]]" in md
    assert "type: moc" in md
