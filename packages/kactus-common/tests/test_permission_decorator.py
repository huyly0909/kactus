"""Tests for the @permission decorator."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kactus_common.authorization.casbin_service import CasbinService
from kactus_common.authorization.const import PermissionAct
from kactus_common.authorization.decorator import permission
from kactus_common.exceptions import PermissionDeniedError


class FakePermission:
    def __init__(self, value: str):
        self.value = value


PROJECT = FakePermission("project")


def _make_request(
    *,
    user_id: int = 1,
    is_superuser: bool = False,
    project_id: int | None = 42,
):
    """Build a mock Request with state attributes."""
    user = SimpleNamespace(id=user_id, is_superuser=is_superuser)
    state = SimpleNamespace(user=user, project_id=project_id)
    request = MagicMock()
    request.state = state
    return request


def _make_casbin_svc(enforce_result: bool = True):
    """Build a mock CasbinService."""
    svc = MagicMock(spec=CasbinService)
    svc.enforce.return_value = enforce_result
    return svc


def _run(coro):
    """Synchronous wrapper for async coroutines."""
    return asyncio.run(coro)


class TestPermissionDecorator:
    def test_superuser_bypasses(self):
        """Superusers should skip all checks."""

        @permission(PROJECT, PermissionAct.manage)
        async def endpoint(request, session):
            return "ok"

        request = _make_request(is_superuser=True)
        result = _run(endpoint(request=request, session=MagicMock()))
        assert result == "ok"

    def test_no_project_raises(self):
        """Should raise when no project is selected."""

        @permission(PROJECT, PermissionAct.read)
        async def endpoint(request, session):
            return "ok"

        request = _make_request(project_id=None)
        with pytest.raises(PermissionDeniedError, match="No project selected"):
            _run(endpoint(request=request, session=MagicMock()))

    def test_not_a_member_raises(self):
        """Should raise when user isn't a project member."""

        @permission(PROJECT, PermissionAct.read)
        async def endpoint(request, session):
            return "ok"

        request = _make_request()
        mock_session = AsyncMock()

        with patch("kactus_common.project.service.ProjectService") as mock_ps:
            mock_ps.get_member_role = AsyncMock(return_value=None)

            with pytest.raises(PermissionDeniedError, match="not a member"):
                _run(endpoint(request=request, session=mock_session))

    def test_permission_denied_raises(self):
        """Should raise when Casbin enforcement fails."""

        @permission(PROJECT, PermissionAct.manage)
        async def endpoint(request, session):
            return "ok"

        request = _make_request()
        mock_session = AsyncMock()
        mock_casbin = _make_casbin_svc(enforce_result=False)

        with (
            patch("kactus_common.project.service.ProjectService") as mock_ps,
            patch(
                "kactus_common.authorization.casbin_service.get_casbin_service",
                return_value=mock_casbin,
            ),
        ):
            mock_ps.get_member_role = AsyncMock(return_value="member")

            with pytest.raises(PermissionDeniedError, match="Insufficient permissions"):
                _run(endpoint(request=request, session=mock_session))

    def test_permission_allowed(self):
        """Should proceed when Casbin enforcement passes."""

        @permission(PROJECT, PermissionAct.read)
        async def endpoint(request, session):
            return "ok"

        request = _make_request()
        mock_session = AsyncMock()
        mock_casbin = _make_casbin_svc(enforce_result=True)

        with (
            patch("kactus_common.project.service.ProjectService") as mock_ps,
            patch(
                "kactus_common.authorization.casbin_service.get_casbin_service",
                return_value=mock_casbin,
            ),
        ):
            mock_ps.get_member_role = AsyncMock(return_value="member")
            result = _run(endpoint(request=request, session=mock_session))

        assert result == "ok"
        mock_casbin.enforce.assert_called_once_with(
            "member", PROJECT, PermissionAct.read
        )

    def test_no_request_raises(self):
        """Should raise if request can't be found."""

        @permission(PROJECT, PermissionAct.read)
        async def endpoint(session):
            return "ok"

        with pytest.raises(PermissionDeniedError, match="Cannot resolve"):
            _run(endpoint(session=MagicMock()))

    def test_no_session_raises(self):
        """Should raise if session is missing (wrong decorator order)."""

        @permission(PROJECT, PermissionAct.read)
        async def endpoint(request):
            return "ok"

        request = _make_request()
        with pytest.raises(PermissionDeniedError, match="Session not available"):
            _run(endpoint(request=request))
