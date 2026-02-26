"""Tests for CasbinService — Casbin-based RBAC enforcer."""

from __future__ import annotations

import pytest
from kactus_common.authorization.casbin_service import CasbinService
from kactus_common.authorization.const import PermissionAct


class FakePermission(str):
    """Fake Permission StrEnum for testing.

    Inherits from ``str`` just like the real ``Permission`` base class,
    so ``str(instance)`` returns the value directly.
    """


class FakeRole(str):
    """Fake DefaultRole StrEnum for testing."""


OWNER = FakeRole("owner")
MANAGER = FakeRole("manager")
MEMBER = FakeRole("member")
PROJECT = FakePermission("project")
BILLING = FakePermission("billing")


@pytest.fixture
def casbin_svc() -> CasbinService:
    """Create a CasbinService loaded with test policies."""
    svc = CasbinService()
    svc.load_from_role_permissions(
        {
            OWNER: [(PROJECT, PermissionAct.manage)],
            MANAGER: [(PROJECT, PermissionAct.write)],
            MEMBER: [(PROJECT, PermissionAct.read)],
        }
    )
    return svc


class TestCasbinServiceEnforce:
    """Test permission enforcement with PermissionAct hierarchy."""

    def test_owner_has_manage(self, casbin_svc: CasbinService):
        assert casbin_svc.enforce("owner", "project", PermissionAct.manage)

    def test_owner_has_write(self, casbin_svc: CasbinService):
        """manage implies write."""
        assert casbin_svc.enforce("owner", "project", PermissionAct.write)

    def test_owner_has_read(self, casbin_svc: CasbinService):
        """manage implies read."""
        assert casbin_svc.enforce("owner", "project", PermissionAct.read)

    def test_manager_has_write(self, casbin_svc: CasbinService):
        assert casbin_svc.enforce("manager", "project", PermissionAct.write)

    def test_manager_has_read(self, casbin_svc: CasbinService):
        """write implies read."""
        assert casbin_svc.enforce("manager", "project", PermissionAct.read)

    def test_manager_cannot_manage(self, casbin_svc: CasbinService):
        assert not casbin_svc.enforce("manager", "project", PermissionAct.manage)

    def test_member_has_read(self, casbin_svc: CasbinService):
        assert casbin_svc.enforce("member", "project", PermissionAct.read)

    def test_member_cannot_write(self, casbin_svc: CasbinService):
        assert not casbin_svc.enforce("member", "project", PermissionAct.write)

    def test_member_cannot_manage(self, casbin_svc: CasbinService):
        assert not casbin_svc.enforce("member", "project", PermissionAct.manage)

    def test_unknown_role_denied(self, casbin_svc: CasbinService):
        assert not casbin_svc.enforce("viewer", "project", PermissionAct.read)

    def test_unknown_permission_denied(self, casbin_svc: CasbinService):
        assert not casbin_svc.enforce("owner", "billing", PermissionAct.read)


class TestCasbinServiceQueries:
    """Test permission query methods."""

    def test_get_role_permissions_owner(self, casbin_svc: CasbinService):
        perms = casbin_svc.get_role_permissions("owner")
        assert ("project", "manage") in perms
        assert ("project", "write") in perms
        assert ("project", "read") in perms

    def test_get_role_permissions_member(self, casbin_svc: CasbinService):
        perms = casbin_svc.get_role_permissions("member")
        assert ("project", "read") in perms
        assert ("project", "write") not in perms

    def test_get_role_permissions_unknown(self, casbin_svc: CasbinService):
        perms = casbin_svc.get_role_permissions("unknown")
        assert perms == []

    def test_get_role_permissions_none(self, casbin_svc: CasbinService):
        perms = casbin_svc.get_role_permissions(None)
        assert perms == []

    def test_get_all_permissions(self, casbin_svc: CasbinService):
        perms = casbin_svc.get_all_permissions()
        assert ("project", "manage") in perms
        assert ("project", "write") in perms
        assert ("project", "read") in perms

    def test_get_all_roles(self, casbin_svc: CasbinService):
        roles = casbin_svc.get_all_roles()
        assert "owner" in roles
        assert "manager" in roles
        assert "member" in roles


class TestMultiplePermissions:
    """Test loading multiple permissions across features."""

    def test_multiple_features(self):
        svc = CasbinService()
        svc.load_from_role_permissions(
            {
                OWNER: [
                    (PROJECT, PermissionAct.manage),
                    (BILLING, PermissionAct.manage),
                ],
                MANAGER: [
                    (PROJECT, PermissionAct.write),
                    (BILLING, PermissionAct.read),
                ],
                MEMBER: [
                    (PROJECT, PermissionAct.read),
                ],
            }
        )

        # Owner can manage both
        assert svc.enforce("owner", "project", PermissionAct.manage)
        assert svc.enforce("owner", "billing", PermissionAct.manage)

        # Manager can write project, only read billing
        assert svc.enforce("manager", "project", PermissionAct.write)
        assert svc.enforce("manager", "billing", PermissionAct.read)
        assert not svc.enforce("manager", "billing", PermissionAct.write)

        # Member can only read project, nothing for billing
        assert svc.enforce("member", "project", PermissionAct.read)
        assert not svc.enforce("member", "billing", PermissionAct.read)
