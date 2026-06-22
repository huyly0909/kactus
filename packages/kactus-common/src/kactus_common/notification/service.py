"""Notification channel service — DB CRUD with owner scoping.

Stateless static methods, mirroring :class:`kactus_common.portfolio.service`.
Channels are user-owned: reads assert ownership via :meth:`get_owned_or_404`.
Config is validated against its per-type schema on create/update.
"""

from __future__ import annotations

import time

from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import NotFoundError, ValidationError
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import NotificationChannelType
from .model import NotificationChannel
from .schema import parse_channel_config


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
    async def get_owned_or_404(
        session: AsyncSession, *, channel_id: int, owner_id: int
    ) -> NotificationChannel:
        """Fetch a channel and assert ``owner_id`` owns it.

        Raises ``NotFoundError`` if missing or owned by someone else — we do not
        leak existence of other users' channels.
        """
        channel = await NotificationChannel.get(session, channel_id)
        if channel is None or channel.owner_id != owner_id:
            raise NotFoundError(f"NotificationChannel record, pk: {channel_id}")
        return channel

    @staticmethod
    async def list_for_owner(
        session: AsyncSession, owner_id: int
    ) -> list[NotificationChannel]:
        """All non-deleted channels owned by ``owner_id``."""
        return await NotificationChannel.all(session, owner_id=owner_id)

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
