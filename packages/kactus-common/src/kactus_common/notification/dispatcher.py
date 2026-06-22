"""Notifier — render a :class:`NotificationEvent` and deliver it to a channel.

Shared infrastructure: it joins the persisted channel (this package's ORM model)
with the channel/template registries, so **any** package may send a
notification — ``from kactus_common.notification.dispatcher import Notifier``.
Channels are blocking, so the send is wrapped in ``asyncio.to_thread`` (gương
``await asyncio.to_thread(provider.read, …)`` in the portfolio API). Transport
errors surface as ``ExternalServiceError``.
"""

from __future__ import annotations

import asyncio

import requests
from kactus_common.exceptions import ExternalServiceError

from .channel import BaseNotificationChannel, RenderedMessage
from .const import NotificationChannelType
from .model import NotificationChannel
from .registry import build_channel, get_template
from .schema import NotificationEvent


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
        channel: NotificationChannel, event: NotificationEvent
    ) -> None:
        """Render ``event`` with the channel's template and deliver it."""
        ctype = NotificationChannelType(channel.channel_type)
        impl = build_channel(ctype, channel.config)  # config decrypted on ORM load
        rendered = get_template(ctype).render(event)
        try:
            await asyncio.to_thread(_send_blocking, impl, rendered)
        except requests.RequestException as exc:
            raise ExternalServiceError(
                f"Failed to send to {ctype} channel: {exc}"
            ) from exc

    @staticmethod
    async def test(channel: NotificationChannel) -> bool:
        """Validate the channel's credentials/config. ``False`` on transport error."""
        ctype = NotificationChannelType(channel.channel_type)
        impl = build_channel(ctype, channel.config)
        try:
            return await asyncio.to_thread(_test_blocking, impl)
        except requests.RequestException:
            return False
