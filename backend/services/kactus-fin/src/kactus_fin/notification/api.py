"""Notification API — user-owned channels, CRUD + test + send.

Channels are user-owned: every route resolves ownership via
``request.state.user`` (mirrors the portfolio API). Secrets in ``config`` are
masked on the way out; sends/tests run through the :class:`Notifier`.
"""

from __future__ import annotations

from fastapi import Request
from kactus_common.config import settings
from kactus_common.exceptions import ExternalServiceError
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import MessageResponse, Pagination
from kactus_fin.dependencies import provide_session
from kactus_notification.const import NotificationChannelType
from kactus_notification.dispatcher import Notifier
from kactus_notification.model import NotificationChannel, NotificationLog
from kactus_notification.queue import enqueue
from kactus_notification.schema import (
    NotificationChannelCreateRequest,
    NotificationChannelSchema,
    NotificationChannelUpdateRequest,
    NotificationEvent,
    NotificationLogSchema,
    mask_config,
)
from kactus_notification.service import (
    NotificationChannelService,
    NotificationLogService,
)
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_schema(channel: NotificationChannel) -> NotificationChannelSchema:
    """Build the public schema with secrets masked."""
    ctype = NotificationChannelType(channel.channel_type)
    return NotificationChannelSchema(
        id=channel.id,
        owner_id=channel.owner_id,
        name=channel.name,
        channel_type=ctype,
        is_active=channel.is_active,
        config=mask_config(ctype, channel.config or {}),
        last_used_at=channel.last_used_at,
    )


def _log_to_schema(log: NotificationLog) -> NotificationLogSchema:
    """Build the public schema for one audit log row."""
    return NotificationLogSchema(
        id=log.id,
        channel_id=log.channel_id,
        channel_type=NotificationChannelType(log.channel_type),
        event_title=log.event_title,
        level=log.level,
        status=log.status,
        trigger=log.trigger,
        attempts=log.attempts,
        error=log.error,
        started_at=log.started_at,
        finished_at=log.finished_at,
    )


# --------------------------------------------------------------------------- #
# Channel CRUD
# --------------------------------------------------------------------------- #
@router.post("")
@provide_session
async def create_channel(
    body: NotificationChannelCreateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Create a notification channel owned by the current user."""
    user = request.state.user
    channel = await NotificationChannelService.create(
        session,
        owner_id=user.id,
        name=body.name,
        channel_type=body.channel_type,
        config=body.config,
    )
    return _to_schema(channel)


@router.get("")
@provide_session
async def list_channels(
    request: Request, session: AsyncSession
) -> Pagination[NotificationChannelSchema]:
    """List the current user's notification channels."""
    user = request.state.user
    channels = await NotificationChannelService.list_for_owner(session, user.id)
    items = [_to_schema(c) for c in channels]
    return Pagination(total=len(items), items=items)


@router.get("/{channel_id}")
@provide_session
async def get_channel(
    channel_id: int, request: Request, session: AsyncSession
) -> NotificationChannelSchema:
    """Get one channel (must be owned by the current user)."""
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    return _to_schema(channel)


@router.put("/{channel_id}")
@provide_session
async def update_channel(
    channel_id: int,
    body: NotificationChannelUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> NotificationChannelSchema:
    """Update a channel's name / active flag / config."""
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    channel = await NotificationChannelService.update(
        session, channel, name=body.name, is_active=body.is_active, config=body.config
    )
    return _to_schema(channel)


@router.delete("/{channel_id}")
@provide_session
async def delete_channel(
    channel_id: int, request: Request, session: AsyncSession
) -> MessageResponse:
    """Logically delete a channel."""
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    await NotificationChannelService.delete(session, channel)
    return MessageResponse(message="deleted")


# --------------------------------------------------------------------------- #
# Test + send
# --------------------------------------------------------------------------- #
@router.post("/{channel_id}/test")
@provide_session
async def test_channel(
    channel_id: int, request: Request, session: AsyncSession
) -> MessageResponse:
    """Validate the channel's credentials/config (e.g. Telegram getMe)."""
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    if not await Notifier.test(channel):
        raise ExternalServiceError("Channel test failed — check the credentials/config")
    await NotificationChannelService.mark_used(session, channel)
    return MessageResponse(message="ok")


def _queue_enabled() -> bool:
    """Whether sends go through the Redis Streams queue.

    Both conditions are real: the queue needs Redis, and ``memory`` is a
    supported single-worker mode where there is none.  Falling back to the
    inline send there keeps dev and the test suite working without a broker
    instead of failing at ``XADD``.
    """
    return (
        getattr(settings, "notification_queue_enabled", True)
        and getattr(settings, "coordination_backend", "memory") == "redis"
    )


@router.post("/{channel_id}/send", status_code=202)
@provide_session
async def send_to_channel(
    channel_id: int,
    body: NotificationEvent,
    request: Request,
    session: AsyncSession,
) -> MessageResponse:
    """Queue an event for delivery on this channel.

    202 in both modes.  The caller cannot do anything with the transport result
    — ``send_event`` already retries and writes ``NotificationLog`` — so a
    stable "accepted" contract beats a status that changes with the deployment's
    coordination backend.  ``GET /{channel_id}/logs`` is where the outcome is.

    ``POST /{channel_id}/test`` stays synchronous on purpose: there the user is
    sitting in front of a form waiting to hear whether the credentials work.
    """
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )

    if _queue_enabled():
        message_id = await enqueue(channel_id=channel.id, owner_id=user.id, event=body)
        logger.info(f"Queued notification {message_id} for channel {channel.id}")
        return MessageResponse(message="queued")

    await Notifier.send_event(session, channel, body)
    await NotificationChannelService.mark_used(session, channel)
    return MessageResponse(message="sent")


@router.get("/{channel_id}/logs")
@provide_session
async def list_channel_logs(
    channel_id: int,
    request: Request,
    session: AsyncSession,
    limit: int = 50,
) -> Pagination[NotificationLogSchema]:
    """List a channel's send history (most-recent-first, owner-scoped)."""
    user = request.state.user
    # Assert ownership before exposing logs (raises 404 otherwise).
    await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    logs = await NotificationLogService.list_for_owner(
        session, user.id, channel_id=channel_id, limit=limit
    )
    items = [_log_to_schema(log) for log in logs]
    return Pagination(total=len(items), items=items)
