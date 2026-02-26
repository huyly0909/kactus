"""Project-related constants and enums."""

from __future__ import annotations

from enum import Enum

from kactus_common.authorization.const import Permission


class ProjectPermission(Permission):
    """Permissions specific to the project feature."""

    project = "project"


class DefaultRole(str, Enum):
    """Default roles available across all packages."""

    OWNER = "owner"
    MANAGER = "manager"
    MEMBER = "member"


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
