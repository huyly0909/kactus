"""User service — database operations for users and sessions."""

from __future__ import annotations

import datetime
import uuid

from kactus_common.database.oltp.models import utcnow
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .const import SESSION_EXPIRY_SECONDS, SESSION_REMEMBER_EXPIRY_SECONDS
from .model import User, UserSession


class UserService:
    """Stateless database operations for User and UserSession."""

    # -------------------------------------------------------------------
    # User queries
    # -------------------------------------------------------------------

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        """Find a user by email address."""
        return await User.first(session, email=email)

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
        """Find a user by primary key."""
        return await User.get(session, user_id)

    # -------------------------------------------------------------------
    # Session management
    # -------------------------------------------------------------------

    @staticmethod
    async def create_session(
        session: AsyncSession,
        user_id: int,
        *,
        remember: bool = False,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_expiry: int = SESSION_EXPIRY_SECONDS,
        remember_expiry: int = SESSION_REMEMBER_EXPIRY_SECONDS,
    ) -> UserSession:
        """Create a new user session and persist it."""
        expiry_seconds = remember_expiry if remember else session_expiry
        now = utcnow()

        user_session = UserSession.init(
            user_id=user_id,
            session_id=uuid.uuid4().hex,
            expires_at=now + datetime.timedelta(seconds=expiry_seconds),
            is_remember=remember,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await user_session.save(session)
        return user_session

    @staticmethod
    async def get_by_session_id(
        session: AsyncSession, session_id: str
    ) -> tuple[UserSession | None, User | None]:
        """Look up a session and its associated user.

        Returns ``(user_session, user)`` or ``(None, None)`` if not found / expired.
        """
        user_session = await UserSession.first(session, session_id=session_id)
        if user_session is None:
            return None, None

        # Check server-side expiration
        if user_session.expires_at < utcnow():
            await session.delete(user_session)
            await session.commit()
            return None, None

        user = await User.get(session, user_session.user_id)
        return user_session, user

    @staticmethod
    async def delete_session(session: AsyncSession, session_id: str) -> None:
        """Delete a single session by its session_id."""
        stmt = delete(UserSession).where(UserSession.session_id == session_id)
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def delete_user_sessions(session: AsyncSession, user_id: int) -> None:
        """Delete all sessions for a user (e.g. on password change)."""
        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def update_last_login(session: AsyncSession, user: User) -> None:
        """Update the user's last_login timestamp."""
        user.last_login = utcnow()
        await user.save(session)
