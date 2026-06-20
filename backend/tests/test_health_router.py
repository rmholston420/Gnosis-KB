"""Tests for gnosis/routers/health.py — readiness + liveness probes."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# ping — trivial liveness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping_returns_pong():
    from gnosis.routers.health import ping
    result = await ping()
    assert result == {"status": "pong"}


# ---------------------------------------------------------------------------
# health — readiness (all checks pass)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_all_ok():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())

    mock_response = MagicMock()
    mock_response.status_code = None

    # Mock httpx async client
    qdrant_resp = MagicMock()
    qdrant_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=qdrant_resp)

    with patch("gnosis.routers.health.shutil.disk_usage") as mock_disk, \
         patch("httpx.AsyncClient", return_value=mock_client):
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)  # 10 GiB free
        result = await health(response=mock_response, db=db)

    assert result["status"] == "healthy"
    assert result["checks"]["database"] == "ok"
    assert result["checks"]["qdrant"] == "ok"
    assert "ok" in result["checks"]["disk"]
    assert "uptime_seconds" in result


@pytest.mark.asyncio
async def test_health_db_failure_returns_degraded():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("DB down"))

    mock_response = MagicMock()
    mock_response.status_code = None

    qdrant_resp = MagicMock()
    qdrant_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=qdrant_resp)

    with patch("gnosis.routers.health.shutil.disk_usage") as mock_disk, \
         patch("httpx.AsyncClient", return_value=mock_client):
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)
        result = await health(response=mock_response, db=db)

    assert result["status"] == "degraded"
    assert mock_response.status_code == 503
    assert "error" in result["checks"]["database"]


@pytest.mark.asyncio
async def test_health_qdrant_failure_returns_degraded():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())

    mock_response = MagicMock()
    mock_response.status_code = None

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=Exception("Qdrant unreachable"))

    with patch("gnosis.routers.health.shutil.disk_usage") as mock_disk, \
         patch("httpx.AsyncClient", return_value=mock_client):
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)
        result = await health(response=mock_response, db=db)

    assert result["status"] == "degraded"
    assert "error" in result["checks"]["qdrant"]


@pytest.mark.asyncio
async def test_health_low_disk_returns_degraded():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())

    mock_response = MagicMock()
    mock_response.status_code = None

    qdrant_resp = MagicMock()
    qdrant_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=qdrant_resp)

    with patch("gnosis.routers.health.shutil.disk_usage") as mock_disk, \
         patch("httpx.AsyncClient", return_value=mock_client):
        # 100 MiB — below the 500 MiB threshold
        mock_disk.return_value = MagicMock(free=100 * 1024 ** 2)
        result = await health(response=mock_response, db=db)

    assert result["status"] == "degraded"
    assert "low" in result["checks"]["disk"]


@pytest.mark.asyncio
async def test_health_qdrant_non_200_status():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    mock_response = MagicMock()
    mock_response.status_code = None

    qdrant_resp = MagicMock()
    qdrant_resp.status_code = 503
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=qdrant_resp)

    with patch("gnosis.routers.health.shutil.disk_usage") as mock_disk, \
         patch("httpx.AsyncClient", return_value=mock_client):
        mock_disk.return_value = MagicMock(free=10 * 1024 ** 3)
        result = await health(response=mock_response, db=db)

    assert result["status"] == "degraded"
    assert "503" in result["checks"]["qdrant"]


@pytest.mark.asyncio
async def test_health_disk_error_returns_degraded():
    from gnosis.routers.health import health

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    mock_response = MagicMock()
    mock_response.status_code = None

    qdrant_resp = MagicMock()
    qdrant_resp.status_code = 200
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=qdrant_resp)

    with patch("gnosis.routers.health.shutil.disk_usage", side_effect=OSError("no path")), \
         patch("httpx.AsyncClient", return_value=mock_client):
        result = await health(response=mock_response, db=db)

    assert result["status"] == "degraded"
    assert "error" in result["checks"]["disk"]
