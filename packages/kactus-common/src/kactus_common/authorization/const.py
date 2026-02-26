"""Authorization constants — PermissionAct and Permission."""

from __future__ import annotations

from enum import IntEnum, StrEnum


class PermissionAct(IntEnum):
    """Permission level — higher value grants more access.

    A user with ``manage`` can do everything ``write`` and ``read`` can.

    Usage::

        if user_act >= PermissionAct.write:
            ...  # user can write
    """

    read = 1
    write = 5
    manage = 10

    @property
    def satisfies(self) -> list[PermissionAct]:
        """All acts this level can perform (self and below)."""
        return [a for a in PermissionAct if a.value <= self.value]


class Permission(StrEnum):
    """Base permission enum — each feature adds its own entries.

    Subclass in feature packages to add feature-specific permissions::

        class ProjectPermission(Permission):
            project = "project"
    """
