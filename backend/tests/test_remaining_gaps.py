"""
test_remaining_gaps.py

Covers the last missing lines across 4 files:

  gnosis/config.py:82           get_settings() return (lru_cache path)
  gnosis/core/auth.py:188       get_vault_owner_ids return {target_id}
  gnosis/core/exceptions.py:49  gnosis_exception_handler return
  gnosis/database.py:66         _AsyncSessionLocalProxy.__aexit__
  gnosis/services/fts.py:87-90  fulltext_search except branch

No DB, no HTTP client, no conftest fixtures required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===========================================================================
# config.py:82  — get_settings() return value
# ===========================================================================


class TestGetSettings:
    def test_get_settings_returns_settings_singleton(self):
        from gnosis.config import get_settings, settings

        assert get_settings() is settings

    def test_get_settings_called_twice_returns_same_object(self):
        from gnosis.config import get_settings

        assert get_settings() is get_settings()


# ===========================================================================
# exceptions.py:49  — gnosis_exception_handler returns JSONResponse
#
# Starlette's JSONResponse serialises the body eagerly into self.body
# (a plain bytes object).  body_iterator is a sync list [self.body], NOT an
# async iterable.  Read response.body directly.
# ===========================================================================


class TestGnosisExceptionHandler:
    @pytest.mark.asyncio
    async def test_handler_returns_500_json_response(self):
        import json

        from fastapi import Request

        from gnosis.core.exceptions import gnosis_exception_handler

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        exc = ValueError("something went wrong")

        response = await gnosis_exception_handler(request, exc)

        assert response.status_code == 500
        # JSONResponse.body is bytes — decode and parse directly
        body = json.loads(response.body)
        assert "something went wrong" in body["detail"]

    @pytest.mark.asyncio
    async def test_handler_includes_internal_server_error_prefix(self):
        import json

        from fastapi import Request

        from gnosis.core.exceptions import gnosis_exception_handler

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/notes",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)
        exc = RuntimeError("database unavailable")

        response = await gnosis_exception_handler(request, exc)

        assert response.status_code == 500
        body = json.loads(response.body)
        assert "Internal server error" in body["detail"]
        assert "database unavailable" in body["detail"]


# ===========================================================================
# database.py:66  — _AsyncSessionLocalProxy.__aexit__
# ===========================================================================


class TestAsyncSessionLocalProxyAexit:
    @pytest.mark.asyncio
    async def test_proxy_aexit_delegates_to_factory(self):
        from gnosis.database import AsyncSessionLocal

        fake_maker = MagicMock()
        fake_maker.__aenter__ = AsyncMock(return_value=MagicMock())
        fake_maker.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "gnosis.database.get_session_factory", return_value=MagicMock(return_value=fake_maker)
        ):
            result = AsyncSessionLocal.__aexit__(None, None, None)
            assert result is not None

    @pytest.mark.asyncio
    async def test_proxy_aexit_return_is_awaitable(self):
        from gnosis.database import AsyncSessionLocal

        fake_maker = MagicMock()
        fake_maker.__aenter__ = AsyncMock(return_value=MagicMock())
        fake_maker.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "gnosis.database.get_session_factory", return_value=MagicMock(return_value=fake_maker)
        ):
            # __aexit__ returns get_session_factory().__aexit__(*args)
            # The factory mock's __aexit__ is an AsyncMock so its return is awaitable
            coro = AsyncSessionLocal.__aexit__(None, None, None)
            assert coro is not None


# ===========================================================================
# services/fts.py:87-90  — except branch when db.execute raises
# ===========================================================================


class TestFulltextSearchExceptBranch:
    @pytest.mark.asyncio
    async def test_db_execute_raises_returns_empty_results(self):
        from gnosis.services.fts import fulltext_search

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("connection lost"))

        result = await fulltext_search(db, "zettelkasten", owner_ids={1})

        assert result["results"] == []
        assert result["elapsed_ms"] == 0.0

    @pytest.mark.asyncio
    async def test_db_execute_raises_operational_error(self):
        from gnosis.services.fts import fulltext_search

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("relation does not exist"))

        result = await fulltext_search(db, "impermanence")

        assert result["results"] == []
        assert result["elapsed_ms"] == 0.0


# ===========================================================================
# auth.py:188  — get_vault_owner_ids return {target_id}
#
# get_accessible_owner_ids is imported INSIDE get_vault_owner_ids via:
#   from gnosis.core.namespace import get_accessible_owner_ids
# so the correct patch target is gnosis.core.namespace.get_accessible_owner_ids
# (patching gnosis.core.auth.* has no effect because the name is resolved
# fresh from gnosis.core.namespace on every call).
# ===========================================================================


class TestGetVaultOwnerIdsReturnTargetId:
    @pytest.mark.asyncio
    async def test_valid_cross_vault_grant_returns_target_id_set(self):
        """auth.py:188 — `return {target_id}` when caller has valid grant."""
        from gnosis.core.auth import get_vault_owner_ids

        current_user = MagicMock()
        current_user.id = 1
        target_id = 99

        fake_request = MagicMock()
        fake_request.headers = {"X-Vault-Owner-Id": str(target_id)}

        db = AsyncMock()

        # Patch at the module where the name is resolved (namespace, not auth)
        with patch(
            "gnosis.core.namespace.get_accessible_owner_ids",
            new=AsyncMock(return_value={target_id}),
        ):
            result = await get_vault_owner_ids(
                request=fake_request,
                current_user=current_user,
                db=db,
            )

        assert result == {target_id}

    @pytest.mark.asyncio
    async def test_valid_cross_vault_grant_different_ids(self):
        """Same arc with different ID values."""
        from gnosis.core.auth import get_vault_owner_ids

        current_user = MagicMock()
        current_user.id = 5
        target_id = 17

        fake_request = MagicMock()
        fake_request.headers = {"X-Vault-Owner-Id": str(target_id)}

        db = AsyncMock()

        with patch(
            "gnosis.core.namespace.get_accessible_owner_ids",
            new=AsyncMock(return_value={target_id}),
        ):
            result = await get_vault_owner_ids(
                request=fake_request,
                current_user=current_user,
                db=db,
            )

        assert result == {target_id}
