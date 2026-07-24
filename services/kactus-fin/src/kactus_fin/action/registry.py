"""What each :class:`ActionType` actually does.

Handlers take ``(session, user_id, params)`` and return a short sentence for the
user.  They are ordinary service calls — the interesting part of this feature is
everything around them (signature, expiry, one-time consumption, GET-does-not-
execute), not the actions themselves.

**Ownership is re-checked in every handler.**  It would be tempting to say the
token already proves authorisation, but the token was issued minutes ago against
state that may have changed: a portfolio can be deleted or transferred between
issue and click.  ``get_owned_or_404`` is cheap and it is the same check the
regular API does.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from kactus_common.exceptions import InvalidArgumentError, NotFoundError
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_common.portfolio.service import PortfolioService
from kactus_fin import data_client
from kactus_notification.model import NotificationChannel
from sqlalchemy.ext.asyncio import AsyncSession

from .const import ActionType

ActionHandler = Callable[[AsyncSession, int, dict], Awaitable[str]]


def _require(params: dict, key: str):
    """Params are signed, but signed is not the same as valid — check anyway."""
    if key not in params or params[key] in (None, ""):
        raise InvalidArgumentError(f"Action params are missing '{key}'")
    return params[key]


async def _add_item(session: AsyncSession, user_id: int, params: dict) -> str:
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=int(_require(params, "portfolio_id")), owner_id=user_id
    )
    asset_type = AssetType(_require(params, "asset_type"))
    code = str(_require(params, "code")).upper()
    await PortfolioService.add_item(
        session, portfolio_id=portfolio.id, asset_type=asset_type, code=code
    )
    return f"Added {asset_type}:{code} to {portfolio.name}"


async def _remove_item(session: AsyncSession, user_id: int, params: dict) -> str:
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=int(_require(params, "portfolio_id")), owner_id=user_id
    )
    asset_type = AssetType(_require(params, "asset_type"))
    code = str(_require(params, "code")).upper()
    await PortfolioService.remove_item(
        session, portfolio_id=portfolio.id, asset_type=asset_type, code=code
    )
    return f"Removed {asset_type}:{code} from {portfolio.name}"


async def _refresh(session: AsyncSession, user_id: int, params: dict) -> str:
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=int(_require(params, "portfolio_id")), owner_id=user_id
    )
    items = await PortfolioService.get_items(session, portfolio.id)
    codes_by_type: dict[str, list[str]] = {}
    for item in items:
        codes_by_type.setdefault(item.asset_type, []).append(item.code)
    if not codes_by_type:
        return f"{portfolio.name} is empty — nothing to refresh"

    # Same path as POST /portfolios/{id}/refresh: a command, so HTTP to the data
    # plane, with dedup so an approval racing the scheduler costs one crawl.
    await data_client.trigger_crawl(
        kind=CrawlKind.QUOTES,
        codes_by_type=codes_by_type,
        trigger=CrawlTrigger.MANUAL,
        portfolio_id=portfolio.id,
        dedup=True,
    )
    return f"Refreshing market data for {portfolio.name}"


async def _mute_channel(session: AsyncSession, user_id: int, params: dict) -> str:
    channel = await NotificationChannel.get(
        session, int(_require(params, "channel_id"))
    )
    if channel is None or channel.owner_id != user_id:
        raise NotFoundError("NotificationChannel record")
    channel.is_active = False
    await channel.save(session)
    return f"Muted notifications on {channel.name}"


ACTION_HANDLERS: dict[ActionType, ActionHandler] = {
    ActionType.PORTFOLIO_ADD_ITEM: _add_item,
    ActionType.PORTFOLIO_REMOVE_ITEM: _remove_item,
    ActionType.PORTFOLIO_REFRESH: _refresh,
    ActionType.NOTIFICATION_MUTE_CHANNEL: _mute_channel,
}
