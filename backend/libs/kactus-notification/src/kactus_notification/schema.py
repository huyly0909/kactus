"""Shared notification schemas — base config, API request/response, the event.

Everything here is channel-agnostic. A channel's own config schema and its
endpoint shapes live in ``channels/<type>/schema.py`` and extend
:class:`BaseChannelConfig`; the tables that map a channel type to those schemas
(``CHANNEL_CONFIG_SCHEMAS``, ``SECRET_FIELDS``) live in the sibling ``registry``
module, which is the one place that imports every channel.
"""

from __future__ import annotations

import datetime

from kactus_common.schemas import AwareUTCDatetime, BaseSchema, FancyInt

from .const import (
    NotificationChannelType,
    NotificationLevel,
    NotificationLogStatus,
    NotificationTrigger,
)

# --------------------------------------------------------------------------- #
# Per-type config: one base schema, each channel type extends it.
# --------------------------------------------------------------------------- #


class BaseChannelConfig(BaseSchema):
    """Fields common to every channel config."""

    timeout: float = 10.0  # HTTP timeout (seconds) for the outbound transport


# --------------------------------------------------------------------------- #
# API request / response
# --------------------------------------------------------------------------- #


class NotificationChannelSchema(BaseSchema):
    """Public channel info — ``config`` secrets are masked."""

    id: FancyInt
    owner_id: FancyInt
    name: str
    channel_type: NotificationChannelType
    is_active: bool
    config: dict = {}
    last_used_at: datetime.datetime | None = None


class DeliveryTargetSchema(BaseSchema):
    """Outcome of delivering one message to one conversation (fan-out channels)."""

    thread_id: str
    thread_type: int = 0
    name: str | None = None
    ok: bool
    error: str | None = None


class SendAttemptSchema(BaseSchema):
    """One *failed* transport attempt — the retry history behind ``attempts``."""

    attempt: int
    error: str
    at: AwareUTCDatetime | None = None


class NotificationLogSchema(BaseSchema):
    """One audit row — the final outcome of a :meth:`Notifier.send_event` call.

    ``targets``/``attempt_errors`` carry the detail the list view summarises: who
    received it and what failed on the way. Empty for single-target channels.
    """

    id: FancyInt
    channel_id: FancyInt
    channel_type: NotificationChannelType
    event_title: str
    body: str | None = None
    level: NotificationLevel
    status: NotificationLogStatus
    trigger: NotificationTrigger
    attempts: int
    error: str | None = None
    targets: list[DeliveryTargetSchema] = []
    attempt_errors: list[SendAttemptSchema] = []
    delivered_count: int | None = None
    target_count: int | None = None
    started_at: AwareUTCDatetime | None = None
    finished_at: AwareUTCDatetime | None = None


class Recipient(BaseSchema):
    """A pickable send target for a channel (Zalo friend / group)."""

    id: str
    name: str
    avatar: str | None = None
    is_group: bool = False


class NotificationChannelCreateRequest(BaseSchema):
    """Create body — ``config`` is validated against ``channel_type``'s schema."""

    name: str
    channel_type: NotificationChannelType
    config: dict


class NotificationChannelUpdateRequest(BaseSchema):
    """Partial update — only provided fields change."""

    name: str | None = None
    is_active: bool | None = None
    config: dict | None = None


# --------------------------------------------------------------------------- #
# Neutral event — "what to notify". Templates render it per channel type.
# --------------------------------------------------------------------------- #


class NotificationEvent(BaseSchema):
    """Channel-agnostic notification payload.

    A template (per channel type) turns this into the concrete message a
    channel can send (Telegram HTML text / Slack Block Kit / …).
    """

    title: str
    body: str = ""
    level: NotificationLevel = NotificationLevel.INFO
    fields: list[tuple[str, str]] = []  # (label, value) rows
    url: str | None = None
