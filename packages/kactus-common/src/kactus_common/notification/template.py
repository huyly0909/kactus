"""Event templates — one :class:`BaseEventTemplate` per channel type.

A template renders the neutral :class:`NotificationEvent` into a
:class:`RenderedMessage` in the format that channel type expects (Telegram HTML
text / Slack Block Kit). The right template is loaded by channel type via the
registry — so the *what* (event) and the *how* (per-channel rendering) stay
decoupled.
"""

from __future__ import annotations

import html
from abc import ABC, abstractmethod
from typing import ClassVar

from .channel import RenderedMessage
from .const import NotificationChannelType, NotificationLevel
from .schema import NotificationEvent


class BaseEventTemplate(ABC):
    """Render a neutral event into a channel-native message."""

    channel_type: ClassVar[NotificationChannelType]

    @abstractmethod
    def render(self, event: NotificationEvent) -> RenderedMessage:
        """Produce the channel-ready payload for ``event``."""


class TelegramEventTemplate(BaseEventTemplate):
    """Telegram HTML rendering (works with ``parse_mode=HTML``)."""

    channel_type = NotificationChannelType.TELEGRAM
    _ICON: dict[NotificationLevel, str] = {
        NotificationLevel.INFO: "ℹ️",
        NotificationLevel.WARNING: "⚠️",
        NotificationLevel.CRITICAL: "🚨",
    }

    def render(self, event: NotificationEvent) -> RenderedMessage:
        icon = self._ICON.get(event.level, "")
        lines = [f"{icon} <b>{html.escape(event.title)}</b>".strip()]
        if event.body:
            lines.append(html.escape(event.body))
        for label, value in event.fields:
            lines.append(f"<b>{html.escape(label)}:</b> {html.escape(value)}")
        if event.url:
            lines.append(f'<a href="{html.escape(event.url, quote=True)}">🔗 link</a>')
        return RenderedMessage(text="\n".join(lines))


class SlackEventTemplate(BaseEventTemplate):
    """Slack Block Kit rendering."""

    channel_type = NotificationChannelType.SLACK
    _EMOJI: dict[NotificationLevel, str] = {
        NotificationLevel.INFO: ":information_source:",
        NotificationLevel.WARNING: ":warning:",
        NotificationLevel.CRITICAL: ":rotating_light:",
    }

    def render(self, event: NotificationEvent) -> RenderedMessage:
        emoji = self._EMOJI.get(event.level, "")
        blocks: list[dict] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {event.title}".strip(),
                },
            }
        ]
        if event.body:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": event.body}}
            )
        if event.fields:
            blocks.append(
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*{label}:* {value}"}
                        for label, value in event.fields
                    ],
                }
            )
        if event.url:
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"<{event.url}|🔗 link>"},
                }
            )
        # `text` is the notification fallback (shown in push notifications).
        return RenderedMessage(
            text=event.title, payload={"text": event.title, "blocks": blocks}
        )
