"""Notification domain enums.

``StrEnum`` so values round-trip cleanly through the DB (stored as strings,
like ``AssetType``) and JSON, and dispatch into the channel/template registries.
"""

from __future__ import annotations

from enum import StrEnum

# Placeholder shown instead of a secret config value in API responses. Lives
# here rather than next to SECRET_FIELDS so modules that only *compare* against
# it (the service's masked-secret merge) need not import the registry.
SECRET_MASK = "***"


class NotificationChannelType(StrEnum):
    """A delivery target. Adding a type = one ``channels/<type>/`` package plus
    one line in each table in :mod:`kactus_notification.registry`."""

    TELEGRAM = "telegram"
    SLACK = "slack"
    ZALO_PA = "zalo_pa"  # Zalo Personal Account (unofficial; QR login via zlapi)


class NotificationLevel(StrEnum):
    """Severity of a notification event — drives template styling (icon/colour)."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationLogStatus(StrEnum):
    """Outcome of a single send (recorded in the audit log)."""

    SUCCESS = "success"
    FAILED = "failed"


class NotificationTrigger(StrEnum):
    """What initiated a send — manual API call vs (future) event-driven auto-fire.

    ``TEST`` covers the two probe endpoints (``/test`` credential check and the
    Zalo ``/test-message`` greeting): they are real outcomes worth auditing, but
    filtering them out of "did my alert go through?" must stay possible.
    """

    MANUAL = "manual"
    EVENT = "event"
    TEST = "test"
