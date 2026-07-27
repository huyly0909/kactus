"""Notifier — render a :class:`NotificationEvent` and deliver it to a channel.

Shared infrastructure: it joins the persisted channel (this package's ORM model)
with the channel/template registries, so **any** package may send a
notification — ``from kactus_notification.dispatcher import Notifier``.
Channels are blocking, so the send is wrapped in ``asyncio.to_thread`` (gương
``await asyncio.to_thread(provider.read, …)`` in the portfolio API). Transport
errors surface as ``ExternalServiceError``.
"""

from __future__ import annotations

import asyncio

import requests
from kactus_common.config import settings
from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import ExternalServiceError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from .channel import BaseNotificationChannel, RenderedMessage
from .const import NotificationChannelType, NotificationLogStatus, NotificationTrigger
from .model import NotificationChannel
from .registry import build_channel, get_template
from .schema import NotificationEvent
from .service import NotificationLogService


def _send_blocking(impl: BaseNotificationChannel, rendered: RenderedMessage) -> None:
    with impl:  # create_connection / close_connection
        impl.send(rendered)


def _test_blocking(impl: BaseNotificationChannel) -> bool:
    with impl:
        return impl.test_connection()


class Notifier:
    """Render + deliver a :class:``NotificationEvent` to a stored channel."""

    @staticmethod
    async def send_event(
        session: AsyncSession,
        channel: NotificationChannel,
        event: NotificationEvent,
        *,
        trigger: NotificationTrigger = NotificationTrigger.MANUAL,
    ) -> None:
        """Render ``event`` and deliver it with synchronous bounded retry.

        Transport errors (``impl.retryable_exceptions``) are retried up to
        ``notification_max_send_attempts`` with exponential backoff; deterministic
        failures (``ExternalServiceError`` — e.g. expired session) are not. Every
        outcome (success or final failure) is written to :class:`NotificationLog`
        so callers — the API now, event-driven auto-fire later — get audit + retry
        for free. Raises ``ExternalServiceError`` when all attempts are exhausted.

        An **inactive** channel is skipped silently (no send, no log) — this is
        the single enforcement point for ``is_active``, covering both the inline
        API path and the queue consumer.
        """
        if not channel.is_active:
            logger.warning(
                "Skipping send to inactive {ctype} channel {cid}",
                ctype=channel.channel_type,
                cid=channel.id,
            )
            return
        ctype = NotificationChannelType(channel.channel_type)
        impl = build_channel(ctype, channel.config)  # config decrypted on ORM load
        rendered = get_template(ctype).render(event)

        max_attempts = max(1, settings.notification_max_send_attempts)
        base_delay = settings.notification_retry_base_delay
        attempts = 0
        last_err: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            try:
                await asyncio.to_thread(_send_blocking, impl, rendered)
                await NotificationLogService.record(
                    session,
                    channel=channel,
                    event=event,
                    status=NotificationLogStatus.SUCCESS,
                    attempts=attempts,
                    error=None,
                    trigger=trigger,
                    finished_at=utcnow(),
                )
                return
            except impl.retryable_exceptions as exc:  # transient transport error
                last_err = exc
                logger.warning(
                    "Notification send to {ctype} channel {cid} failed "
                    "(attempt {n}/{max}): {exc}",
                    ctype=ctype,
                    cid=channel.id,
                    n=attempt,
                    max=max_attempts,
                    exc=exc,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(base_delay * 2 ** (attempt - 1))
            except ExternalServiceError as exc:  # deterministic — do not retry
                last_err = exc
                break

        await NotificationLogService.record(
            session,
            channel=channel,
            event=event,
            status=NotificationLogStatus.FAILED,
            attempts=attempts,
            error=str(last_err),
            trigger=trigger,
            finished_at=utcnow(),
        )
        raise ExternalServiceError(
            f"Failed to send to {ctype} channel after {attempts} attempt(s): "
            f"{last_err}"
        ) from last_err

    @staticmethod
    async def test(channel: NotificationChannel) -> bool:
        """Validate the channel's credentials/config. ``False`` on transport error."""
        ctype = NotificationChannelType(channel.channel_type)
        impl = build_channel(ctype, channel.config)
        try:
            return await asyncio.to_thread(_test_blocking, impl)
        except requests.RequestException:
            return False
