"""Portfolio market-data events.

A crawl run that writes fresh data dispatches :class:`MarketDataRefreshedPayload`.
The SSE layer subscribes (via ``register_handler``) and fans the nudge out to all
connected browsers, which then re-fetch the affected query keys.

IMPORTANT: crawls run *outside* a request (scheduler / CLI), so dispatch MUST use
``background=False`` — the composite dispatcher routes background dispatch through
fastapi-events (request-scoped) and foreground through blinker.  See
``kactus_common.events.backends.composite``.
"""

from __future__ import annotations

from kactus_common.events.interface import BaseEventName, BaseEventPayload


class MarketEventName(BaseEventName):
    """Event names for the portfolio/market-data domain."""

    data_refreshed = "data_refreshed"


class MarketDataRefreshedPayload(BaseEventPayload):
    """Emitted when a crawl writes fresh market data for some codes."""

    __event_name__ = MarketEventName.data_refreshed

    asset_type: str
    kind: str
    codes: list[str] = []
    crawl_run_id: int | None = None
