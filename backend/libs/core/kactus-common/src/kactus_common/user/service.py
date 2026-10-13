"""User service — database operations for users and sessions."""

from __future__ import annotations

import datetime
import hashlib
import uuid

from kactus_common.database.oltp.models import utcnow
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .const import SESSION_EXPIRY_SECONDS, SESSION_REMEMBER_EXPIRY_SECONDS
from .model import User, UserSession


def hash_session_id(raw: str) -> str:
    """SHA-256 (hex) of a session token — what ``user_sessions`` stores.

    The cookie carries the raw token; the table only ever sees its hash, so a
    read of the table (dump, backup, replica) cannot be replayed as a login.
    A fast unsalted hash is enough: the token is 122 random bits, not a
    guessable password.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


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

    @staticmethod
    async def get_password_hash(session: AsyncSession, user_id: int) -> str | None:
        """Read the raw bcrypt hash from the DB, bypassing PasswordHash mask.

        Uses ``text()`` raw SQL so the TypeDecorator's
        ``process_result_value`` is never applied.
        """
        from sqlalchemy import text

        stmt = text("SELECT password_hash FROM users WHERE id = :uid")
        result = await session.execute(stmt, {"uid": user_id})
        row = result.first()
        return row[0] if row else None

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
    ) -> str:
        """Create a new user session, persist its hash, return the raw token.

        This is the only moment the raw token exists server-side — it goes
        into the cookie and nowhere else.
        """
        expiry_seconds = remember_expiry if remember else session_expiry
        now = utcnow()
        token = uuid.uuid4().hex

        user_session = UserSession.init(
            user_id=user_id,
            session_hash=hash_session_id(token),
            expires_at=now + datetime.timedelta(seconds=expiry_seconds),
            is_remember=remember,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await user_session.save(session)
        return token

    @staticmethod
    async def get_by_session_id(
        session: AsyncSession, session_id: str
    ) -> tuple[UserSession | None, User | None]:
        """Look up a session (by the raw cookie token) and its associated user.

        Returns ``(user_session, user)`` or ``(None, None)`` if not found / expired.
        """
        user_session = await UserSession.first(
            session, session_hash=hash_session_id(session_id)
        )
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
        """Delete a single session by its raw cookie token."""
        stmt = delete(UserSession).where(
            UserSession.session_hash == hash_session_id(session_id)
        )
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

    @staticmethod
    async def update_preferences(
        session: AsyncSession,
        user: User,
        *,
        language: str | None = None,
        timezone: str | None = None,
    ) -> User:
        """Update the user's UI preferences (partial — only provided keys)."""
        if language is not None:
            user.language = language
        if timezone is not None:
            user.timezone = timezone
        await user.save(session)
        return user
