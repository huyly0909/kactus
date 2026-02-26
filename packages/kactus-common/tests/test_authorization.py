"""Tests for PasswordHash TypeDecorator and authorization registry."""

from __future__ import annotations

from kactus_common.crypto import hash_password, verify_password
from kactus_common.database.oltp.types import PasswordHash


class TestPasswordHash:
    """Test the PasswordHash TypeDecorator."""

    def test_process_bind_param_hashes_plaintext(self):
        """Plaintext password should be bcrypt-hashed on bind."""
        pw = PasswordHash()
        result = pw.process_bind_param("my_secure_password", dialect=None)

        assert result is not None
        assert result != "my_secure_password"
        assert result.startswith("$2b$")  # bcrypt prefix
        assert verify_password("my_secure_password", result)

    def test_process_bind_param_none_passthrough(self):
        """None should pass through unchanged."""
        pw = PasswordHash()
        assert pw.process_bind_param(None, dialect=None) is None

    def test_process_bind_param_mask_passthrough(self):
        """The mask value should not be re-hashed."""
        pw = PasswordHash()
        result = pw.process_bind_param(PasswordHash.MASK, dialect=None)
        assert result == PasswordHash.MASK

    def test_process_result_value_returns_mask(self):
        """Any stored hash should return the mask on read."""
        pw = PasswordHash()
        fake_hash = hash_password("test")
        result = pw.process_result_value(fake_hash, dialect=None)
        assert result == "********"

    def test_process_result_value_none(self):
        """None should return None."""
        pw = PasswordHash()
        assert pw.process_result_value(None, dialect=None) is None


class TestAuthorizationRegistry:
    """Test the RoleRegistry class."""

    def test_default_roles_loaded(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        assert registry.has_role("owner")
        assert registry.has_role("manager")
        assert registry.has_role("member")

    def test_add_role_with_inheritance(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        registry.grant("manager", "project:read")
        registry.add_role("staff", inherits="manager")

        # staff should have all manager permissions
        manager_perms = registry.get_permissions("manager")
        staff_perms = registry.get_permissions("staff")
        for perm in manager_perms:
            assert perm in staff_perms

    def test_grant_extra_permission(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        registry.add_role("staff", inherits="manager")
        registry.grant("staff", "billing:read")

        assert registry.has_permission("staff", "billing:read")
        assert not registry.has_permission("manager", "billing:read")

    def test_standalone_role(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        registry.add_role("customer")
        registry.grant("customer", "invoice:read")

        assert registry.has_permission("customer", "invoice:read")
        assert not registry.has_permission("customer", "project:read")

    def test_get_all_roles(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        registry.add_role("custom")
        roles = registry.get_all_roles()
        assert "custom" in roles
        assert "owner" in roles

    def test_duplicate_add_role_noop(self):
        from kactus_common.authorization.registry import RoleRegistry

        registry = RoleRegistry()
        original_perms = registry.get_permissions("member")
        registry.add_role("member")  # should be a no-op
        assert registry.get_permissions("member") == original_perms


class TestProjectConsts:
    """Test project constants."""

    def test_default_role_values(self):
        from kactus_common.project.const import DefaultRole

        assert DefaultRole.OWNER == "owner"
        assert DefaultRole.MANAGER == "manager"
        assert DefaultRole.MEMBER == "member"

    def test_project_status_values(self):
        from kactus_common.project.const import ProjectStatus

        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.ARCHIVED == "archived"
