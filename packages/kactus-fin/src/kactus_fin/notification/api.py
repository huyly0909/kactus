"""Notification API — user-owned channels, CRUD + test + send.

Channels are user-owned: every route resolves ownership via
``request.state.user`` (mirrors the portfolio API). Secrets in ``config`` are
masked on the way out; sends/tests run through the :class:`Notifier`.
"""

from __future__ import annotations

from fastapi import Request
from kactus_common.exceptions import ExternalServiceError
from kactus_common.notification.const import NotificationChannelType
from kactus_common.notification.dispatcher import Notifier
from kactus_common.notification.model import NotificationChannel
from kactus_common.notification.schema import (
    NotificationChannelCreateRequest,
    NotificationChannelSchema,
    NotificationChannelUpdateRequest,
    NotificationEvent,
    mask_config,
)
from kactus_common.notification.service import NotificationChannelService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import MessageResponse, Pagination
from kactus_fin.dependencies import provide_session
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


@router.post("/{channel_id}/send")
@provide_session
async def send_to_channel(
    channel_id: int,
    body: NotificationEvent,
    request: Request,
    session: AsyncSession,
) -> MessageResponse:
    """Render an event with the channel's template and deliver it."""
    user = request.state.user
    channel = await NotificationChannelService.get_owned_or_404(
        session, channel_id=channel_id, owner_id=user.id
    )
    await Notifier.send_event(channel, body)
    await NotificationChannelService.mark_used(session, channel)
    return MessageResponse(message="sent")
