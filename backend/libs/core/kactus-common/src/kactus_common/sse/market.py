"""Bridge market events → the SSE broker.

Registered by whichever process *runs crawls* — after the data-plane split that
is kactus-data-server, not kactus-fin. The crawl emits ``data_refreshed`` in
its own process; this handler publishes it to the broker, and on the Redis
backend every kactus-fin worker's listener picks it up and pushes it to the
browsers it holds. Nobody has to know which process holds which connection.

``register_sse_handler`` MUST be called BEFORE the scheduler starts: blinker
(used for foreground/scheduler-context dispatch) raises ``KeyError`` on dispatch
if no handler is registered for the event yet.

Note the consequence of the split: with ``coordination_backend="memory"`` the
handler publishes into the crawling process's own in-memory broker and no
browser ever sees it — the two planes are different processes by construction.
Redis is not an optimisation here, it is the only wiring that works.
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


def reset_sse_handler() -> None:
    """Forget the registration (tests re-register against a fresh broker)."""
    global _registered
    _registered = False
