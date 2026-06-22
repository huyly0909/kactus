"""Notification domain ORM models (channel-type agnostic).

A channel is identified by ``channel_type`` + a typed ``config`` blob, so a new
delivery target is a new provider/template — not a migration. ``config`` holds
credentials, so it is encrypted at rest via :class:`EncryptedJSON`.
"""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import (
    AuditMixin,
    Base,
    LogicalDeleteMixin,
    ModelMixin,
)
from kactus_common.database.oltp.types import EncryptedJSON, UnsignedBigInt
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .const import NotificationChannelType


class NotificationChannel(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    """A user-owned delivery target (Telegram chat, Slack webhook, …)."""

    __tablename__ = "notification_channels"

    owner_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255))
    channel_type: Mapped[str] = mapped_column(
        String(16), default=NotificationChannelType.TELEGRAM
    )
    # Encrypted at rest — secrets (bot token / webhook url) never stored plaintext.
    config: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
