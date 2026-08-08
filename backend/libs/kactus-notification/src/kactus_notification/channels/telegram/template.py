"""Telegram event rendering."""

from __future__ import annotations

import html

from ...channel import RenderedMessage
from ...const import NotificationChannelType, NotificationLevel
from ...schema import NotificationEvent
from ...template import BaseEventTemplate


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
