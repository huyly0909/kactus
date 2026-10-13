"""Zalo Personal Account channel — config, transport, template, QR onboarding."""

from .channel import ZaloPAChannel
from .schema import ZaloPAChannelConfig, ZaloRecipientTarget
from .template import ZaloPAEventTemplate

__all__ = [
    "ZaloPAChannel",
    "ZaloPAChannelConfig",
    "ZaloPAEventTemplate",
    "ZaloRecipientTarget",
]
