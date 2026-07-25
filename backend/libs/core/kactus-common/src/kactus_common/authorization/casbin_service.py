"""Casbin-based authorization service — in-memory RBAC enforcer.

Policies are auto-populated at startup from ``KactusApp.role_permissions``
declarations.  The ``PermissionAct`` hierarchy is expanded when policies
are loaded so that ``manage`` also grants ``write`` and ``read``.

Usage::

    from kactus_common.authorization.casbin_service import CasbinService

    casbin_svc = CasbinService()
    casbin_svc.load_from_role_permissions(role_permissions)

    if casbin_svc.enforce("owner", "project", PermissionAct.write):
        ...  # allowed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import casbin
from kactus_common.authorization.const import PermissionAct

if TYPE_CHECKING:
    from kactus_common.authorization.const import Permission
    from kactus_common.project.const import DefaultRole

# Casbin model — simple (role, permission, act) RBAC
_MODEL_TEXT = """
[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = r.sub == p.sub && r.obj == p.obj && r.act == p.act
"""


class CasbinService:
    """In-memory Casbin enforcer for project-scoped RBAC.

    Policies are loaded once at startup from ``KactusApp.role_permissions``.
    The ``PermissionAct`` hierarchy is automatically expanded:
    ``manage`` → also grants ``write`` and ``read``.
    ``write``  → also grants ``read``.
    """

    def __init__(self) -> None:
        model = casbin.Model()
        model.load_model_from_text(_MODEL_TEXT)
        self._enforcer = casbin.Enforcer(model)
        self._role_permission_map: dict[str, list[tuple[str, str]]] = {}

    def load_from_role_permissions(
        self,
        role_permissions: dict[DefaultRole, list[tuple[Permission, PermissionAct]]],
    ) -> None:
        """Populate Casbin policies from KactusApp role_permissions.

        Expands the PermissionAct hierarchy so that higher acts
        automatically grant lower acts.

        Args:
            role_permissions: ``{DefaultRole: [(Permission, PermissionAct), ...]}``.
        """
        self._role_permission_map.clear()

        for role, perm_tuples in role_permissions.items():
            role_str = str(role)
            for perm, act in perm_tuples:
                perm_str = str(perm)
                # Expand hierarchy: manage → write, read; write → read
                for satisfied_act in act.satisfies:
                    act_str = satisfied_act.name
                    policy = [role_str, perm_str, act_str]
                    if not self._enforcer.has_policy(*policy):
                        self._enforcer.add_policy(*policy)

                    # Track for get_role_permissions
                    self._role_permission_map.setdefault(role_str, [])
                    pair = (perm_str, act_str)
                    if pair not in self._role_permission_map[role_str]:
                        self._role_permission_map[role_str].append(pair)

    def enforce(
        self,
        role: str,
        permission: str | Permission,
        act: PermissionAct | str,
    ) -> bool:
        """Check if a role has a permission at the given act level.

        Args:
            role: Role name (e.g. ``"owner"``).
            permission: Permission code (e.g. ``"project"``).
            act: Required permission act (e.g. ``PermissionAct.write``).

        Returns:
            ``True`` if the role is allowed, ``False`` otherwise.
        """
        perm_str = str(permission)
        act_str = act.name if isinstance(act, PermissionAct) else str(act)
        return self._enforcer.enforce(str(role), perm_str, act_str)

    def get_role_permissions(self, role: str | None) -> list[tuple[str, str]]:
        """Get all (permission, act) pairs for a role.

        Returns:
            List of ``(permission_code, act_name)`` tuples.
        """
        if role is None:
            return []
        return list(self._role_permission_map.get(role, []))

    def get_all_permissions(self) -> list[tuple[str, str]]:
        """Get all unique (permission, act) pairs across all roles.

        Useful for superuser — returns the full permission set.
        """
        seen: set[tuple[str, str]] = set()
        result: list[tuple[str, str]] = []
        for pairs in self._role_permission_map.values():
            for pair in pairs:
                if pair not in seen:
                    seen.add(pair)
                    result.append(pair)
        return result

    def get_all_roles(self) -> list[str]:
        """Get all role names with policies loaded."""
        return list(self._role_permission_map.keys())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_casbin_service: CasbinService | None = None


def get_casbin_service() -> CasbinService:
    """Get the global CasbinService singleton.

    Raises ``RuntimeError`` if ``init_casbin_service`` has not been called.
    """
    if _casbin_service is None:
        raise RuntimeError(
            "CasbinService not initialised. "
            "Call init_casbin_service() during app startup."
        )
    return _casbin_service


def init_casbin_service(
    role_permissions: dict,
) -> CasbinService:
    """Create and populate the global CasbinService.

    Called by ``AppManager.init_fastapi()`` after collecting role
    permissions from all registered apps.

    Args:
        role_permissions: Aggregated ``{DefaultRole: [(Permission, PermissionAct), ...]}``.

    Returns:
        The initialised ``CasbinService`` instance.
    """
    global _casbin_service
    _casbin_service = CasbinService()
    _casbin_service.load_from_role_permissions(role_permissions)
    return _casbin_service
