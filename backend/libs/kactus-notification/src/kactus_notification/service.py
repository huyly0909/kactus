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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .const import (
    SECRET_MASK,
    NotificationChannelType,
    NotificationLogStatus,
    NotificationTrigger,
)
from .model import NotificationChannel, NotificationLog
from .registry import SECRET_FIELDS, parse_channel_config
from .schema import NotificationEvent


def _validate_config(channel_type: NotificationChannelType, config: dict) -> None:
    """Validate a config dict, re-raising pydantic errors as 400 ``ValidationError``."""
    try:
        parse_channel_config(channel_type, config)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"Invalid config for {channel_type} channel",
            data={"errors": exc.errors(include_url=False, include_context=False)},
        ) from exc


def _merge_masked_secrets(
    channel_type: NotificationChannelType, incoming: dict, stored: dict
) -> dict:
    """Keep the stored value wherever the incoming config carries the ``***`` mask.

    The API always masks secrets on the way out, so a client that round-trips a
    fetched config would otherwise clobber every credential with ``***``.
    """
    merged = dict(incoming)
    for key in SECRET_FIELDS.get(channel_type, set()):
        if merged.get(key) == SECRET_MASK and key in stored:
            merged[key] = stored[key]
    return merged


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
            ctype = NotificationChannelType(channel.channel_type)
            config = _merge_masked_secrets(ctype, config, channel.config or {})
            _validate_config(ctype, config)
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
        targets: list[dict] | None = None,
        attempt_errors: list[dict] | None = None,
    ) -> NotificationLog:
        """Insert a single log row capturing the final send outcome.

        ``targets`` is the per-conversation outcome for fan-out channels; the
        delivered/total counts are derived from it so callers cannot disagree
        with their own target list.
        """
        log = NotificationLog.init(
            channel_id=channel.id,
            owner_id=channel.owner_id,
            # Set from the parent channel: the queue consumer writes logs with no
            # request context, so project_id cannot come from the ContextVar.
            project_id=channel.project_id,
            channel_type=str(channel.channel_type),
            event_title=event.title,
            body=event.body or None,
            level=str(event.level),
            status=str(status),
            trigger=str(trigger),
            attempts=attempts,
            error=error,
            targets=targets or None,
            attempt_errors=attempt_errors or None,
            delivered_count=(
                sum(1 for t in targets if t.get("ok")) if targets else None
            ),
            target_count=len(targets) if targets else None,
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
        offset: int = 0,
    ) -> tuple[int, list[NotificationLog]]:
        """Most-recent-first logs for a project (optionally one channel).

        ``NotificationLog`` is not ``ProjectScopedMixin`` (the queue consumer
        writes it context-free), so the project scope is applied explicitly here.
        Returns ``(total, page)`` — the total is the *matching row count*, not the
        page size, so the client can page instead of guessing there is one page.
        """
        total_stmt = (
            select(func.count())
            .select_from(NotificationLog)
            .filter_by(project_id=project_id)
        )
        stmt = NotificationLog.select().filter_by(project_id=project_id)
        if channel_id is not None:
            total_stmt = total_stmt.filter_by(channel_id=channel_id)
            stmt = stmt.filter_by(channel_id=channel_id)
        total = int(await session.scalar(total_stmt) or 0)
        stmt = (
            stmt.order_by(NotificationLog.create_time.desc())
            .limit(limit)
            .offset(offset)
        )
        return total, list(await session.scalars(stmt))
