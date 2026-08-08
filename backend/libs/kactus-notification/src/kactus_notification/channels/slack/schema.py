"""Slack config."""

from __future__ import annotations

from ...schema import BaseChannelConfig


class SlackChannelConfig(BaseChannelConfig):
    """Slack Incoming Webhook config."""

    webhook_url: str
