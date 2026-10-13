"""Zalo PA event rendering (plain text)."""

from __future__ import annotations

from ...channel import RenderedMessage
from ...const import NotificationChannelType, NotificationLevel
from ...schema import NotificationEvent
from ...template import BaseEventTemplate


class ZaloPAEventTemplate(BaseEventTemplate):
    """Zalo PA plain-text rendering — Zalo chat has no rich markup for bots."""

    channel_type = NotificationChannelType.ZALO_PA
    _ICON: dict[NotificationLevel, str] = {
        NotificationLevel.INFO: "ℹ️",
        NotificationLevel.WARNING: "⚠️",
        NotificationLevel.CRITICAL: "🚨",
    }

    def render(self, event: NotificationEvent) -> RenderedMessage:
        icon = self._ICON.get(event.level, "")
        lines = [f"{icon} {event.title}".strip()]
        if event.body:
            lines.append(event.body)
        for label, value in event.fields:
            lines.append(f"{label}: {value}")
        if event.url:
            lines.append(event.url)
        return RenderedMessage(text="\n".join(lines))
