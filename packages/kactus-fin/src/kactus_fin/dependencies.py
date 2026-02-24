"""Application-level dependency injection."""

from __future__ import annotations

from functools import lru_cache

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.user.auth import AuthDependency, create_auth_dependency
from kactus_fin.config import get_settings


@lru_cache
def get_db() -> DatabaseSessionManager:
    """Get the singleton database session manager."""
    settings = get_settings()
    return DatabaseSessionManager(database_url=settings.database_url)


@lru_cache
def get_auth() -> AuthDependency:
    """Get the singleton auth dependency."""
    settings = get_settings()
    return create_auth_dependency(
        db=get_db(),
        cookie_secure=settings.session_cookie_secure,
        session_expiry=settings.session_expiry,
        remember_expiry=settings.session_remember_expiry,
    )


def get_db_session():
    """FastAPI dependency — yields a database session."""
    return get_db().get_session()
