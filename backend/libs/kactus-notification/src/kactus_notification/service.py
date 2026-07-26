"""Notification channel service — DB CRUD with project scoping.

Stateless static methods, mirroring :class:`kactus_common.portfolio.service`.
Channels are shared within a project: reads resolve via the project-scoped
:meth:`get_or_404` (the global ``ProjectScopedMixin`` filter enforces the
boundary). ``owner_id`` is retained only as an audit of who created the channel.
Config is validated against its per-type schema on create/update.
"""

from __future__ import annotations

import datetime
import time

from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import ValidationError
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import NotificationChannelType, NotificationLogStatus, NotificationTrigger
from .model import NotificationChannel, NotificationLog
from .schema import NotificationEvent, parse_channel_config


def _validate_config(channel_type: NotificationChannelType, config: dict) -> None:
    """Validate a config dict, re-raising pydantic errors as 400 ``ValidationError``."""
    try:
        parse_channel_config(channel_type, config)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"Invalid config for {channel_type} channel",
            data={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc


class NotificationChannelService:
    """CRUD for user-owned notification channels."""

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        owner_id: int,
        name: str,
        channel_type: NotificationChannelType,
        config: dict,
    ) -> NotificationChannel:
        """Create a channel owned by ``owner_id`` (config validated by type)."""
        _validate_config(channel_type, config)
        channel = NotificationChannel.init(
            owner_id=owner_id,
            name=name,
            channel_type=str(channel_type),
            config=config,
            created_by=owner_id,
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        return channel

    @staticmethod
    async def get_or_404(session: AsyncSession, channel_id: int) -> NotificationChannel:
        """Fetch a channel in the current project, or raise ``NotFoundError``.

        Uses a ``SELECT`` (not ``session.get``) so the global project filter
        applies — a channel in another project reads as missing, never leaking
        its existence across projects.
        """
        return await NotificationChannel.first_or_404(session, id=channel_id)

    @staticmethod
    async def list_for_project(
        session: AsyncSession,
    ) -> list[NotificationChannel]:
        """All non-deleted channels in the current project.

        Scoped transparently by the global ``ProjectScopedMixin`` SELECT filter.
        """
        return await NotificationChannel.all(session)

    @staticmethod
    async def update(
        session: AsyncSession,
        channel: NotificationChannel,
        *,
        name: str | None = None,
        is_active: bool | None = None,
        config: dict | None = None,
    ) -> NotificationChannel:
        """Update mutable channel fields (config re-validated against its type)."""
        if name is not None:
            channel.name = name
        if is_active is not None:
            channel.is_active = is_active
        if config is not None:
            _validate_config(NotificationChannelType(channel.channel_type), config)
            channel.config = config
        await channel.save(session)
        return channel

    @staticmethod
    async def delete(session: AsyncSession, channel: NotificationChannel) -> None:
        """Logically delete a channel."""
        channel.deleted_timestamp = int(time.time())
        await channel.save(session)

    @staticmethod
    async def mark_used(
        session: AsyncSession, channel: NotificationChannel
    ) -> NotificationChannel:
        """Stamp ``last_used_at`` after a successful send/test."""
        channel.last_used_at = utcnow()
        await channel.save(session)
        return channel


class NotificationLogService:
    """Append-only audit log for sends (gương ``CrawlRunService``).

    One row per :meth:`Notifier.send_event` outcome — ``attempts`` counts the
    transport retries, ``status`` is the final result. Never updated after write.
    """

    @staticmethod
    async def record(
        session: AsyncSession,
        *,
        channel: NotificationChannel,
        event: NotificationEvent,
        status: NotificationLogStatus,
        attempts: int,
        error: str | None,
        trigger: NotificationTrigger = NotificationTrigger.MANUAL,
        finished_at: datetime.datetime | None = None,
    ) -> NotificationLog:
        """Insert a single log row capturing the final send outcome."""
        log = NotificationLog.init(
            channel_id=channel.id,
            owner_id=channel.owner_id,
            # Set from the parent channel: the queue consumer writes logs with no
            # request context, so project_id cannot come from the ContextVar.
            project_id=channel.project_id,
            channel_type=str(channel.channel_type),
            event_title=event.title,
            level=str(event.level),
            status=str(status),
            trigger=str(trigger),
            attempts=attempts,
            error=error,
            finished_at=finished_at,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log

    @staticmethod
    async def list_for_project(
        session: AsyncSession,
        project_id: int,
        *,
        channel_id: int | None = None,
        limit: int = 50,
    ) -> list[NotificationLog]:
        """Most-recent-first logs for a project (optionally one channel).

        ``NotificationLog`` is not ``ProjectScopedMixin`` (the queue consumer
        writes it context-free), so the project scope is applied explicitly here.
        """
        stmt = NotificationLog.select().filter_by(project_id=project_id)
        if channel_id is not None:
            stmt = stmt.filter_by(channel_id=channel_id)
        stmt = stmt.order_by(NotificationLog.create_time.desc()).limit(limit)
        return list(await session.scalars(stmt))
