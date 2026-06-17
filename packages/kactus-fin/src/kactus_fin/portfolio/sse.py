"""SSE handler registration — bridges market events → the SSE broker.

``register_sse_handler`` MUST be called BEFORE the scheduler starts: blinker
(used for foreground/scheduler-context dispatch) raises ``KeyError`` on dispatch
if no handler is registered for the event yet.
"""

from __future__ import annotations

from kactus_common.events import register_handler
from kactus_common.portfolio.events import MarketDataRefreshedPayload, MarketEventName
from kactus_common.sse.broker import get_sse_broker
from loguru import logger

_registered = False


def register_sse_handler() -> None:
    """Idempotently wire ``data_refreshed`` → broker fan-out."""
    global _registered
    if _registered:
        return

    broker = get_sse_broker()

    @register_handler(MarketEventName.data_refreshed)
    async def _on_data_refreshed(
        *, event_name: MarketEventName, payload: MarketDataRefreshedPayload
    ) -> None:
        await broker.publish(
            {
                "asset_type": payload.asset_type,
                "kind": payload.kind,
                "codes": payload.codes,
                "crawl_run_id": payload.crawl_run_id,
            }
        )

    _registered = True
    logger.info("SSE handler registered for market data_refreshed events")
