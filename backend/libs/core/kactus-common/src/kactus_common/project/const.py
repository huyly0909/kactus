"""Project-related constants and enums."""

from __future__ import annotations

from enum import Enum, StrEnum

from kactus_common.authorization.const import Permission


class ProjectPermission(Permission):
    """Permissions specific to the project feature."""

    project = "project"


class DefaultRole(StrEnum):
    """Default roles available across all packages.

    A ``StrEnum`` (not the old ``(str, Enum)`` idiom) so ``str(DefaultRole.OWNER)``
    is ``"owner"``, matching the role string persisted on ``ProjectMember.role``
    and the Casbin policy subject. With ``(str, Enum)`` it was ``"DefaultRole.OWNER"``,
    so a role read back from the DB never matched its own policy.
    """

    OWNER = "owner"
    MANAGER = "manager"
    MEMBER = "member"


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
