"""Project-related constants and enums."""

from __future__ import annotations

import re
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


#: Display name of the project auto-created with every non-admin user. The
#: identity of that project is its ``user-<id>`` code, never this name — it is
#: free text the owner may rename.
PERSONAL_PROJECT_NAME = "First Project"

#: Max length of ``Project.code``, mirroring the ``String(50)`` column. Enforced
#: in the service because an over-long value is a Postgres
#: ``StringDataRightTruncation`` (a 500), not a validation error, and SQLite —
#: what the tests run on — accepts it silently.
PROJECT_CODE_MAX_LENGTH = 50

#: ``Project.code`` is a URL-safe slug. Kept here rather than only in the
#: frontend's zod schema so the rule has one definition on the side that is
#: actually authoritative.
PROJECT_CODE_PATTERN = re.compile(r"^[a-z0-9-]+$")
