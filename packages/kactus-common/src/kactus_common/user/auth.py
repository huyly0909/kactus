"""Shared auth middleware — reusable across all kactus packages.

Uses the settings registry and ``get_db()`` singleton so no manual
wiring is needed in each package's dependencies module.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import AuthenticationError

from .const import (
    PROJECT_COOKIE_NAME,
    SESSION_COOKIE_NAME,
)
from .model import User
from .service import UserService


@dataclass
class AuthConfig:
    """Auth configuration — reads from settings registry at creation time."""

    cookie_name: str = SESSION_COOKIE_NAME
    project_cookie_name: str = PROJECT_COOKIE_NAME


class AuthDependency:
    """FastAPI auth dependency.

    Obtain via ``get_auth()``::

        from kactus_common.user.auth import get_auth

        auth = get_auth()

        @router.get("/api/auth/me")
        async def me(user: User = Depends(auth.get_current_user)):
            return user
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    async def get_current_user(self, request: Request) -> User:
        """FastAPI dependency — reads session cookie, validates, returns User.

        Also sets:
        * ``request.state.user`` — for access in endpoints/decorators.
        * ``set_current_user_id()`` — for ``AuditMixin`` auto-populate.
        """
        session_id = request.cookies.get(self._config.cookie_name)
        if not session_id:
            raise AuthenticationError("Not authenticated")

        async with get_db().get_session() as session:
            user_session, user = await UserService.get_by_session_id(
                session, session_id
            )

        if user_session is None or user is None:
            raise AuthenticationError("Session expired or invalid")

        # Set ContextVar for AuditMixin auto-populate
        from kactus_common.user.context import set_current_user_id

        set_current_user_id(user.id)

        # Set request.state.user for @permission decorator
        request.state.user = user

        # Read selected project from cookie
        project_id_str = request.cookies.get(self._config.project_cookie_name)
        request.state.project_id = int(project_id_str) if project_id_str else None

        return user

    async def login_user(
        self,
        request: Request,
        response: Response,
        user: User,
        remember: bool = False,
    ) -> str:
        """Create session, set cookie, return session_id."""
        from kactus_common.config import settings

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        async with get_db().get_session() as session:
            user_session = await UserService.create_session(
                session,
                user.id,
                remember=remember,
                ip_address=ip_address,
                user_agent=user_agent,
                session_expiry=settings.session_expiry,
                remember_expiry=settings.session_remember_expiry,
            )
            await UserService.update_last_login(session, user)

        # Set httpOnly cookie
        expiry_seconds = (
            settings.session_remember_expiry if remember else settings.session_expiry
        )
        response.set_cookie(
            key=self._config.cookie_name,
            value=user_session.session_id,
            max_age=expiry_seconds,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )
        return user_session.session_id

    async def logout_user(self, request: Request, response: Response) -> None:
        """Delete session from DB and clear cookie."""
        from kactus_common.config import settings

        session_id = request.cookies.get(self._config.cookie_name)
        if session_id:
            async with get_db().get_session() as session:
                await UserService.delete_session(session, session_id)

        response.delete_cookie(
            key=self._config.cookie_name,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            path="/",
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_auth: AuthDependency | None = None


def get_auth() -> AuthDependency:
    """Return a singleton ``AuthDependency``.

    Reads cookie config from constants.  Session expiry and cookie
    security are read from the settings registry at call time.
    """
    global _auth
    if _auth is None:
        _auth = AuthDependency(AuthConfig())
    return _auth


def clear_auth() -> None:
    """Reset the singleton (useful for testing)."""
    global _auth
    _auth = None
