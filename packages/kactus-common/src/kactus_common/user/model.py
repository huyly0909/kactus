"""User and UserSession ORM models."""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import (
    AuditMixin,
    Base,
    LogicalDeleteMixin,
    ModelMixin,
)
from kactus_common.database.oltp.types import UnsignedBigInt
from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .const import UserStatus


class User(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    """Application user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    last_login: Mapped[datetime.datetime | None] = mapped_column(default=None)


class UserSession(Base, ModelMixin):
    """Active user session — one row per logged-in device."""

    __tablename__ = "user_sessions"

    user_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime.datetime]
    is_remember: Mapped[bool] = mapped_column(default=False)

    # Device / tracing info
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    user_agent: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (
        Index("ix_user_sessions_user_id_session_id", "user_id", "session_id"),
    )
