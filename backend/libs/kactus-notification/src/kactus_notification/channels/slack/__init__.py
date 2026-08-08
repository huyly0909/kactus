"""Slack Incoming Webhook channel — config, transport, template."""

from .channel import SlackChannel
from .schema import SlackChannelConfig
from .template import SlackEventTemplate

__all__ = [
    "SlackChannel",
    "SlackChannelConfig",
    "SlackEventTemplate",
]
