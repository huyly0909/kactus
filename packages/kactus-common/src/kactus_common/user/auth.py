"""Shared auth middleware factory — reusable across all kactus packages."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, Response
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import AuthenticationError

from .const import (
    SESSION_COOKIE_NAME,
    SESSION_EXPIRY_SECONDS,
    SESSION_REMEMBER_EXPIRY_SECONDS,
)
from .model import User
from .service import UserService


@dataclass
class AuthConfig:
    """Per-package auth configuration."""

    db: DatabaseSessionManager
    cookie_name: str = SESSION_COOKIE_NAME
    session_expiry: int = SESSION_EXPIRY_SECONDS
    remember_expiry: int = SESSION_REMEMBER_EXPIRY_SECONDS
    cookie_secure: bool = False
    cookie_samesite: str = "lax"


class AuthDependency:
    """FastAPI auth dependency — created per package via ``create_auth_dependency``.

    Usage in kactus-fin::

        from kactus_common.user.auth import create_auth_dependency

        auth = create_auth_dependency(
            db=db,
            cookie_secure=settings.session_cookie_secure,
        )

        @router.get("/api/auth/me")
        async def me(user: User = Depends(auth.get_current_user)):
            return user
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    async def get_current_user(self, request: Request) -> User:
        """FastAPI dependency — reads session cookie, validates, returns User."""
        session_id = request.cookies.get(self._config.cookie_name)
        if not session_id:
            raise AuthenticationError("Not authenticated")

        async with self._config.db.get_session() as session:
            user_session, user = await UserService.get_by_session_id(
                session, session_id
            )

        if user_session is None or user is None:
            raise AuthenticationError("Session expired or invalid")

        return user

    async def login_user(
        self,
        request: Request,
        response: Response,
        user: User,
        remember: bool = False,
    ) -> str:
        """Create session, set cookie, return session_id."""
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        async with self._config.db.get_session() as session:
            user_session = await UserService.create_session(
                session,
                user.id,
                remember=remember,
                ip_address=ip_address,
                user_agent=user_agent,
                session_expiry=self._config.session_expiry,
                remember_expiry=self._config.remember_expiry,
            )
            await UserService.update_last_login(session, user)

        # Set httpOnly cookie
        expiry_seconds = (
            self._config.remember_expiry if remember else self._config.session_expiry
        )
        response.set_cookie(
            key=self._config.cookie_name,
            value=user_session.session_id,
            max_age=expiry_seconds,
            httponly=True,
            secure=self._config.cookie_secure,
            samesite=self._config.cookie_samesite,
            path="/",
        )
        return user_session.session_id

    async def logout_user(self, request: Request, response: Response) -> None:
        """Delete session from DB and clear cookie."""
        session_id = request.cookies.get(self._config.cookie_name)
        if session_id:
            async with self._config.db.get_session() as session:
                await UserService.delete_session(session, session_id)

        response.delete_cookie(
            key=self._config.cookie_name,
            httponly=True,
            secure=self._config.cookie_secure,
            samesite=self._config.cookie_samesite,
            path="/",
        )


def create_auth_dependency(
    db: DatabaseSessionManager,
    *,
    cookie_name: str = SESSION_COOKIE_NAME,
    session_expiry: int = SESSION_EXPIRY_SECONDS,
    remember_expiry: int = SESSION_REMEMBER_EXPIRY_SECONDS,
    cookie_secure: bool = False,
    cookie_samesite: str = "lax",
) -> AuthDependency:
    """Factory to create an auth dependency for any kactus package.

    Args:
        db: The package's DatabaseSessionManager instance.
        cookie_name: Override the default cookie name.
        session_expiry: Override default session TTL (seconds).
        remember_expiry: Override default remember-me TTL (seconds).
        cookie_secure: Set True in production (HTTPS-only cookies).
        cookie_samesite: SameSite cookie policy.

    Returns:
        An ``AuthDependency`` instance with ``get_current_user``,
        ``login_user``, and ``logout_user`` methods.
    """
    config = AuthConfig(
        db=db,
        cookie_name=cookie_name,
        session_expiry=session_expiry,
        remember_expiry=remember_expiry,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
    )
    return AuthDependency(config)
