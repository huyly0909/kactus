"""Event template base — one subclass per channel type under ``channels/``.

A template renders the neutral :class:`NotificationEvent` into a
:class:`RenderedMessage` in the format that channel type expects (Telegram HTML
text / Slack Block Kit). The right template is loaded by channel type via the
registry — so the *what* (event) and the *how* (per-channel rendering) stay
decoupled.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from .channel import RenderedMessage
from .const import NotificationChannelType
from .schema import NotificationEvent


class BaseEventTemplate(ABC):
    """Render a neutral event into a channel-native message."""

    channel_type: ClassVar[NotificationChannelType]

    @abstractmethod
    def render(self, event: NotificationEvent) -> RenderedMessage:
        """Produce the channel-ready payload for ``event``."""
