"""Role registry — package-level role extension mechanism.

Each package can register additional roles and permissions at startup::

    from kactus_common.authorization.registry import RoleRegistry

    registry = RoleRegistry()

    # Add package-specific roles that inherit from default roles
    registry.add_role("staff", inherits="manager")
    registry.grant("staff", "billing:read")
    registry.grant("staff", "billing:create")

    # Standalone role (no inheritance)
    registry.add_role("customer")
    registry.grant("customer", "invoice:read")
"""

from __future__ import annotations

from kactus_common.project.const import DefaultRole


class RoleRegistry:
    """Manages roles and their permissions, supporting inheritance.

    Roles are accumulated during startup, and the final resolved permission
    map can be retrieved via ``get_all_permissions()``.
    """

    def __init__(self) -> None:
        # Start with default roles (empty permissions — populated by KactusApp)
        self._roles: dict[str, list[str]] = {role.value: [] for role in DefaultRole}
        self._inheritance: dict[str, str] = {}

    def add_role(self, role: str, *, inherits: str | None = None) -> None:
        """Register a new role, optionally inheriting from an existing one.

        Args:
            role: Name of the new role (e.g. ``"staff"``).
            inherits: Parent role to inherit permissions from.
        """
        if role in self._roles:
            return  # already registered

        parent_perms = []
        if inherits and inherits in self._roles:
            parent_perms = list(self._roles[inherits])
            self._inheritance[role] = inherits

        self._roles[role] = parent_perms

    def grant(self, role: str, permission: str) -> None:
        """Grant a permission to a role.

        Args:
            role: Role name.
            permission: Permission string (e.g. ``"billing:read"``).
        """
        if role not in self._roles:
            self._roles[role] = []
        if permission not in self._roles[role]:
            self._roles[role].append(permission)

    def get_permissions(self, role: str) -> list[str]:
        """Get all permissions for a role (including inherited)."""
        return list(self._roles.get(role, []))

    def get_all_roles(self) -> dict[str, list[str]]:
        """Get the full role → permissions map."""
        return {role: list(perms) for role, perms in self._roles.items()}

    def get_role_names(self) -> list[str]:
        """Get all registered role names."""
        return list(self._roles.keys())

    def has_role(self, role: str) -> bool:
        """Check if a role is registered."""
        return role in self._roles

    def has_permission(self, role: str, permission: str) -> bool:
        """Check if a role has a specific permission."""
        return permission in self._roles.get(role, [])
