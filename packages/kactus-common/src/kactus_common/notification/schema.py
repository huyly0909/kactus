"""Notification request/response + per-type config schemas + the neutral event.

Two registries make the feature generic:

* ``CHANNEL_CONFIG_SCHEMAS[type]`` — the Pydantic schema a channel's ``config``
  dict is validated against (base + per-type extension; "load đúng loại").
* ``SECRET_FIELDS[type]``          — config keys masked before leaving the API.

The channel/template *behaviour* registries live in the sibling ``registry``
module (they do I/O); these *data-shape* registries stay here so the persistence
service, the channel impls, and the API masking all share one source of truth.
"""

from __future__ import annotations

import datetime

from kactus_common.schemas import BaseSchema, FancyInt

from .const import NotificationChannelType, NotificationLevel

# --------------------------------------------------------------------------- #
# Per-type config: one base schema, each channel type extends it.
# --------------------------------------------------------------------------- #


class BaseChannelConfig(BaseSchema):
    """Fields common to every channel config."""

    timeout: float = 10.0  # HTTP timeout (seconds) for the outbound transport


class TelegramChannelConfig(BaseChannelConfig):
    """Telegram Bot API config — token + target chat."""

    bot_token: str
    chat_id: str
    parse_mode: str = "HTML"  # HTML | MarkdownV2 | Markdown


class SlackChannelConfig(BaseChannelConfig):
    """Slack Incoming Webhook config."""

    webhook_url: str


CHANNEL_CONFIG_SCHEMAS: dict[NotificationChannelType, type[BaseChannelConfig]] = {
    NotificationChannelType.TELEGRAM: TelegramChannelConfig,
    NotificationChannelType.SLACK: SlackChannelConfig,
}

# Config keys that hold secrets — masked in API responses, encrypted at rest.
SECRET_FIELDS: dict[NotificationChannelType, set[str]] = {
    NotificationChannelType.TELEGRAM: {"bot_token"},
    NotificationChannelType.SLACK: {"webhook_url"},
}

_MASK = "***"


def parse_channel_config(
    channel_type: NotificationChannelType, config: dict
) -> BaseChannelConfig:
    """Validate a raw config dict against its per-type schema.

    Raises ``pydantic.ValidationError`` on a bad/incomplete config — callers
    translate that into a 400 ``ValidationError`` (see the API/service layer).
    """
    return CHANNEL_CONFIG_SCHEMAS[channel_type].model_validate(config or {})


def mask_config(channel_type: NotificationChannelType, config: dict) -> dict:
    """Replace secret values with ``***`` for safe display."""
    secret = SECRET_FIELDS.get(channel_type, set())
    return {k: (_MASK if k in secret else v) for k, v in (config or {}).items()}


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
