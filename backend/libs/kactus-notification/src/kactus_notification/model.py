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
    ProjectScopedMixin,
)
from kactus_common.database.oltp.types import EncryptedJSON, UnsignedBigInt
from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .const import NotificationChannelType, NotificationLevel, NotificationTrigger


class NotificationChannel(
    Base, ModelMixin, AuditMixin, LogicalDeleteMixin, ProjectScopedMixin
):
    """A project-scoped delivery target (Telegram chat, Slack webhook, …).

    ``owner_id`` records the creator (audit); access is governed by the owning
    ``project_id`` + the member's role.
    """

    __tablename__ = "notification_channels"

    owner_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(255))
    channel_type: Mapped[str] = mapped_column(
        String(16), default=NotificationChannelType.TELEGRAM
    )
    # Encrypted at rest — secrets (bot token / webhook url / Zalo session) never
    # stored plaintext.
    config: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(default=None)


class NotificationLog(Base, ModelMixin):
    """Append-only audit record for one send attempt (gương ``CrawlRun``).

    No ``AuditMixin``/``LogicalDeleteMixin`` — logs are immutable and never
    user-edited. ``attempts`` counts transport retries; ``status`` is the final
    outcome. ``started_at`` aliases ``create_time`` for API readability.

    A row answers three questions the UI needs and a bare status/title could not:
    **what** was sent (``body``), **who** received it (``targets``, one entry per
    conversation for fan-out channels) and **why** it took N tries
    (``attempt_errors``, one entry per failed attempt).
    """

    __tablename__ = "notification_logs"

    channel_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    owner_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    # Plain column (NOT ProjectScopedMixin): the queue consumer writes this with
    # no request context, so it is set from the parent channel and filtered
    # explicitly in list queries.
    project_id: Mapped[UnsignedBigInt | None] = mapped_column(index=True, default=None)
    channel_type: Mapped[str] = mapped_column(String(16))
    event_title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    level: Mapped[str] = mapped_column(String(16), default=NotificationLevel.INFO)
    status: Mapped[str] = mapped_column(String(16), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default=NotificationTrigger.MANUAL)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    # [{thread_id, thread_type, name, ok, error}] — empty for single-target
    # channels (Telegram/Slack), one entry per conversation for Zalo PA.
    targets: Mapped[list | None] = mapped_column(JSON, default=None)
    # [{attempt, error, at}] — the retry history the dispatcher used to only log.
    attempt_errors: Mapped[list | None] = mapped_column(JSON, default=None)
    delivered_count: Mapped[int | None] = mapped_column(Integer, default=None)
    target_count: Mapped[int | None] = mapped_column(Integer, default=None)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    @property
    def started_at(self) -> datetime.datetime | None:
        """When the row was written — aliases ``create_time``.

        The row is inserted once the outcome is known, so on a retried send this
        is the *end* of the last attempt, not the start of the first. The real
        per-attempt timeline is in ``attempt_errors``; the UI labels this field
        "Recorded at" rather than claiming otherwise.
        """
        return self.create_time
