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

# CSRF (kactus_common/user/csrf.py). The cookie is app-prefixed, not axios's
# default ``XSRF-TOKEN``: several *.labenry.com apps share ``localhost`` in dev,
# and cookies ignore the port, so a generic name lets one app's login clobber
# another's token. The header is per-request and never collides; it has no
# underscores because nginx silently drops underscored request headers.
CSRF_COOKIE_NAME = "kactus_xsrf_token"
CSRF_HEADER_NAME = "X-XSRF-TOKEN"
CSRF_FORM_FIELD = "csrf_token"  # plain HTML forms only (action-link confirm page)
