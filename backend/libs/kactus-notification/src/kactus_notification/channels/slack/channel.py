"""Slack Incoming Webhook transport."""

from __future__ import annotations

from ...channel import BaseNotificationChannel, RenderedMessage
from ...const import NotificationChannelType
from .schema import SlackChannelConfig


class SlackChannel(BaseNotificationChannel):
    """Slack Incoming Webhook — POST the message body to the webhook URL."""

    channel_type = NotificationChannelType.SLACK
    config_schema = SlackChannelConfig
    _WEBHOOK_PREFIX = "https://hooks.slack.com/"

    def send(self, message: RenderedMessage) -> None:
        cfg: SlackChannelConfig = self.config  # type: ignore[assignment]
        body = (
            message.payload if message.payload is not None else {"text": message.text}
        )
        resp = self.session.post(cfg.webhook_url, json=body, timeout=cfg.timeout)
        resp.raise_for_status()

    def test_connection(self) -> bool:
        # Incoming webhooks have no introspection endpoint — validate URL shape so
        # a "test" doesn't post a stray message to the channel.
        return self.config.webhook_url.startswith(self._WEBHOOK_PREFIX)  # type: ignore[attr-defined]
