"""Notification domain enums.

``StrEnum`` so values round-trip cleanly through the DB (stored as strings,
like ``AssetType``) and JSON, and dispatch into the channel/template registries.
"""

from __future__ import annotations

from enum import StrEnum


class NotificationChannelType(StrEnum):
    """A delivery target. Adding a type = +1 config schema, +1 channel, +1 template."""

    TELEGRAM = "telegram"
    SLACK = "slack"


class NotificationLevel(StrEnum):
    """Severity of a notification event — drives template styling (icon/colour)."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
