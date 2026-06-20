"""Tests for gnosis/routers/vault.py.

Covers: trigger_vault_sync (background + stream modes),
get_sync_status (idle, running, done, error),
_run_sync_background (success + exception),
_sync_sse_generator (success + exception).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _user(uid=1):
    u = MagicMock()
    u.id = uid
    return u


async def _async_gen(*lines):
    for line in lines:
        yield line


# ---------------------------------------------------------------------------
# trigger_vault_sync — background (non-streaming)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_vault_sync_background_returns_202():
    from gnosis.routers.vault import trigger_vault_sync

    bg = MagicMock()
    bg.add_task = MagicMock()
    user = _user(1)

    result = await trigger_vault_sync(background_tasks=bg, stream=False, current_user=user)
    assert result.status == "accepted"
    assert result.user_id == 1
    bg.add_task.assert_called_once()


# ---------------------------------------------------------------------------
# trigger_vault_sync — streaming (SSE)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_vault_sync_stream_returns_streaming_response():
    from fastapi.responses import StreamingResponse
    from gnosis.routers.vault import trigger_vault_sync

    bg = MagicMock()
    user = _user(2)

    with patch("gnosis.routers.vault.run_full_sync_for_user", return_value=_async_gen("synced: a.md")):
        result = await trigger_vault_sync(background_tasks=bg, stream=True, current_user=user)

    assert isinstance(result, StreamingResponse)
    assert result.media_type == "text/event-stream"


# ---------------------------------------------------------------------------
# get_sync_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_sync_status_idle_when_no_entry():
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import get_sync_status

    vault_mod._sync_status.clear()
    user = _user(99)
    result = await get_sync_status(current_user=user)
    assert result.state == "idle"


@pytest.mark.asyncio
async def test_get_sync_status_running():
    import time
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import get_sync_status

    uid = 10
    vault_mod._sync_status[uid] = {
        "state": "running",
        "started": time.time() - 5,
        "files_processed": 3,
        "files_total": 10,
        "last_error": None,
    }
    result = await get_sync_status(current_user=_user(uid))
    assert result.state == "running"
    assert result.files_processed == 3
    assert result.elapsed is not None


@pytest.mark.asyncio
async def test_get_sync_status_done():
    import time
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import get_sync_status

    uid = 11
    vault_mod._sync_status[uid] = {
        "state": "done",
        "started": time.time() - 2,
        "files_processed": 5,
        "files_total": 5,
        "last_error": None,
    }
    result = await get_sync_status(current_user=_user(uid))
    assert result.state == "done"
    assert result.last_error is None


@pytest.mark.asyncio
async def test_get_sync_status_error():
    import time
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import get_sync_status

    uid = 12
    vault_mod._sync_status[uid] = {
        "state": "error",
        "started": time.time() - 1,
        "files_processed": 0,
        "files_total": 0,
        "last_error": "disk full",
    }
    result = await get_sync_status(current_user=_user(uid))
    assert result.state == "error"
    assert result.last_error == "disk full"


# ---------------------------------------------------------------------------
# _run_sync_background
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_sync_background_success():
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import _run_sync_background

    lines = ["total: 3", "synced: a.md", "synced: b.md", "skipped: c.md"]

    with patch("gnosis.routers.vault.run_full_sync_for_user", return_value=_async_gen(*lines)):
        await _run_sync_background(user_id=20)

    status = vault_mod._sync_status[20]
    assert status["state"] == "done"
    assert status["files_processed"] == 3
    assert status["files_total"] == 3


@pytest.mark.asyncio
async def test_run_sync_background_exception_sets_error():
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import _run_sync_background

    async def _fail(uid):
        raise RuntimeError("disk error")
        yield  # make it an async generator

    with patch("gnosis.routers.vault.run_full_sync_for_user", side_effect=RuntimeError("disk error")):
        await _run_sync_background(user_id=21)

    assert vault_mod._sync_status[21]["state"] == "error"
    assert "disk error" in vault_mod._sync_status[21]["last_error"]


# ---------------------------------------------------------------------------
# _sync_sse_generator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sync_sse_generator_yields_sse_lines():
    from gnosis.routers.vault import _sync_sse_generator

    lines = ["total: 2", "synced: x.md", "deleted: y.md"]
    with patch("gnosis.routers.vault.run_full_sync_for_user", return_value=_async_gen(*lines)):
        output = []
        async for chunk in _sync_sse_generator(user_id=30):
            output.append(chunk)

    assert any("[done]" in line for line in output)
    assert any("synced" in line for line in output)


@pytest.mark.asyncio
async def test_sync_sse_generator_yields_error_on_exception():
    from gnosis.routers import vault as vault_mod
    from gnosis.routers.vault import _sync_sse_generator

    with patch("gnosis.routers.vault.run_full_sync_for_user", side_effect=RuntimeError("boom")):
        output = []
        async for chunk in _sync_sse_generator(user_id=31):
            output.append(chunk)

    assert any("[error]" in line for line in output)
    assert vault_mod._sync_status[31]["state"] == "error"
