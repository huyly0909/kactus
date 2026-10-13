"""Channel type → implementation tables. The one module that knows every channel.

Four registries, all keyed by :class:`NotificationChannelType`:

* ``CHANNEL_REGISTRY``        — the transport class (does I/O).
* ``TEMPLATE_REGISTRY``       — the renderer instance (stateless, shared).
* ``CHANNEL_CONFIG_SCHEMAS``  — the Pydantic schema a channel's ``config`` dict
  is validated against ("load đúng loại").
* ``SECRET_FIELDS``           — config keys masked before leaving the API.

They live together because they are the *same* fan-out: adding a channel type
means one new ``channels/<type>/`` package plus one line in each table here.
Keeping them out of ``schema.py`` is also what makes the dependency graph
acyclic — ``channels/*/schema.py`` imports ``BaseChannelConfig`` from
``schema.py``, so ``schema.py`` must not import back.
"""

from __future__ import annotations

from .channel import BaseNotificationChannel
from .channels.slack import SlackChannel, SlackChannelConfig, SlackEventTemplate
from .channels.telegram import (
    TelegramChannel,
    TelegramChannelConfig,
    TelegramEventTemplate,
)
from .channels.zalo_pa import ZaloPAChannel, ZaloPAChannelConfig, ZaloPAEventTemplate
from .const import SECRET_MASK, NotificationChannelType
from .schema import BaseChannelConfig
from .template import BaseEventTemplate

CHANNEL_REGISTRY: dict[NotificationChannelType, type[BaseNotificationChannel]] = {
    NotificationChannelType.TELEGRAM: TelegramChannel,
    NotificationChannelType.SLACK: SlackChannel,
    NotificationChannelType.ZALO_PA: ZaloPAChannel,
}

TEMPLATE_REGISTRY: dict[NotificationChannelType, BaseEventTemplate] = {
    NotificationChannelType.TELEGRAM: TelegramEventTemplate(),
    NotificationChannelType.SLACK: SlackEventTemplate(),
    NotificationChannelType.ZALO_PA: ZaloPAEventTemplate(),
}

CHANNEL_CONFIG_SCHEMAS: dict[NotificationChannelType, type[BaseChannelConfig]] = {
    NotificationChannelType.TELEGRAM: TelegramChannelConfig,
    NotificationChannelType.SLACK: SlackChannelConfig,
    NotificationChannelType.ZALO_PA: ZaloPAChannelConfig,
}

# Config keys that hold secrets — masked in API responses, encrypted at rest.
SECRET_FIELDS: dict[NotificationChannelType, set[str]] = {
    NotificationChannelType.TELEGRAM: {"bot_token"},
    NotificationChannelType.SLACK: {"webhook_url"},
    NotificationChannelType.ZALO_PA: {
        "cookies",
        "imei",
        "zpw_sek",
        "zpsid",
        "secret_key",
    },
}


def build_channel(
    channel_type: NotificationChannelType, config: dict | BaseChannelConfig
) -> BaseNotificationChannel:
    """Instantiate the channel for ``channel_type``, validating its config."""
    cls = CHANNEL_REGISTRY[channel_type]
    cfg = (
        config
        if isinstance(config, BaseChannelConfig)
        else cls.config_schema.model_validate(config)
    )
    return cls(cfg)


def get_template(channel_type: NotificationChannelType) -> BaseEventTemplate:
    """Return the (shared, stateless) template for ``channel_type``."""
    return TEMPLATE_REGISTRY[channel_type]


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
    return {k: (SECRET_MASK if k in secret else v) for k, v in (config or {}).items()}
