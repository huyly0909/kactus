"""User-related constants and enums."""

from __future__ import annotations

from enum import Enum

from kactus_common.authorization.const import Permission


class UserPermission(Permission):
    """Permissions specific to the user feature."""

    user = "user"


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


# ---------------------------------------------------------------------------
# Session defaults — packages can override via their own config
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME = "kactus_session_id"
SESSION_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days
SESSION_REMEMBER_EXPIRY_SECONDS = 365 * 24 * 3600  # 1 year
PROJECT_COOKIE_NAME = "kactus_project_id"
