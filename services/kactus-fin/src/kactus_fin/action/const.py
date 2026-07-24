"""What an action link is allowed to do.

Every member here must correspond to a handler in :mod:`kactus_fin.action.registry`
— the enum is the allow-list, and a token naming anything outside it cannot be
issued.

**There is no buy/sell.** The plan described trading from a notification, but
this codebase has no order-execution domain: portfolios are watchlists, and
nothing anywhere places an order. Registering ``trade.buy`` here backed by
nothing would be a lie in the one place a user is most likely to trust it. When
brokerage integration exists, it is one member plus one handler.
"""

from __future__ import annotations

from enum import StrEnum


class ActionType(StrEnum):
    """Actions that a signed link may execute."""

    PORTFOLIO_ADD_ITEM = "portfolio.add_item"
    PORTFOLIO_REMOVE_ITEM = "portfolio.remove_item"
    PORTFOLIO_REFRESH = "portfolio.refresh"
    NOTIFICATION_MUTE_CHANNEL = "notification.mute_channel"


#: Shown on the confirmation page — the user has to understand what they are
#: about to approve, and the raw enum value does not tell them.
ACTION_LABELS: dict[ActionType, str] = {
    ActionType.PORTFOLIO_ADD_ITEM: "Add an asset to a portfolio",
    ActionType.PORTFOLIO_REMOVE_ITEM: "Remove an asset from a portfolio",
    ActionType.PORTFOLIO_REFRESH: "Refresh a portfolio's market data",
    ActionType.NOTIFICATION_MUTE_CHANNEL: "Mute a notification channel",
}
