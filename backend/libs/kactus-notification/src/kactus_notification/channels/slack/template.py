"""Slack event rendering (Block Kit)."""

from __future__ import annotations

from ...channel import RenderedMessage
from ...const import NotificationChannelType, NotificationLevel
from ...schema import NotificationEvent
from ...template import BaseEventTemplate


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
