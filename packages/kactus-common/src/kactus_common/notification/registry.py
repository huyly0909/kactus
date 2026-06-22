"""Channel + template registries and factories.

``CHANNEL_REGISTRY`` / ``TEMPLATE_REGISTRY`` map ``NotificationChannelType`` to
its channel class / template instance — the dispatch tables that make the
feature generic (gương ``build_providers`` in ``kactus_data.portfolio.provider``).
Adding a type = +1 entry in each registry.
"""

from __future__ import annotations

from .channel import BaseNotificationChannel, SlackChannel, TelegramChannel
from .const import NotificationChannelType
from .schema import BaseChannelConfig
from .template import BaseEventTemplate, SlackEventTemplate, TelegramEventTemplate

CHANNEL_REGISTRY: dict[NotificationChannelType, type[BaseNotificationChannel]] = {
    NotificationChannelType.TELEGRAM: TelegramChannel,
    NotificationChannelType.SLACK: SlackChannel,
}

TEMPLATE_REGISTRY: dict[NotificationChannelType, BaseEventTemplate] = {
    NotificationChannelType.TELEGRAM: TelegramEventTemplate(),
    NotificationChannelType.SLACK: SlackEventTemplate(),
}


def build_channel(
    channel_type: NotificationChannelType, config: dict | BaseChannelConfig
) -> BaseNotificationChannel:
    """Instantiate the channel for ``channel_type``, loading config by type.

    ``config`` may be a raw dict (validated against the type's schema) or an
    already-parsed :class:`BaseChannelConfig`.
    """
    cls = CHANNEL_REGISTRY[channel_type]
    cfg = (
        config
        if isinstance(config, BaseChannelConfig)
        else cls.config_schema.model_validate(config)
    )
    return cls(cfg)


def get_template(channel_type: NotificationChannelType) -> BaseEventTemplate:
    """Return the template for ``channel_type`` ("load đúng template theo loại")."""
    return TEMPLATE_REGISTRY[channel_type]
