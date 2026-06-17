"""In-process SSE broker — async pub/sub fan-out to connected clients.

Single-worker v1: each SSE connection ``subscribe()``s and gets its own bounded
``asyncio.Queue``; ``publish()`` fans a message out to every queue.  Bounded
queues mean a slow/stalled client drops messages instead of back-pressuring the
publisher or leaking memory.

Migration path (documented, not built): swap this for Redis pub/sub so multiple
uvicorn workers can each fan out to their own local subscribers.  The
``publish``/``subscribe`` surface is intentionally Redis-shaped.
"""

from __future__ import annotations

import asyncio

from loguru import logger


class SSEBroker:
    """Fan-out broker for Server-Sent Events."""

    def __init__(self, max_queue: int = 100) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._max_queue = max_queue

    async def subscribe(self) -> asyncio.Queue:
        """Register a new subscriber and return its message queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        logger.debug(f"SSE subscribe — {len(self._subscribers)} active")
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a subscriber (called when its connection closes)."""
        self._subscribers.discard(queue)
        logger.debug(f"SSE unsubscribe — {len(self._subscribers)} active")

    async def publish(self, message: dict) -> None:
        """Fan ``message`` out to all subscribers (non-blocking, drop-on-full)."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full — dropping message")

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# --------------------------------------------------------------------------- #
# Module-level singleton — one broker per process.
# --------------------------------------------------------------------------- #
_broker: SSEBroker | None = None


def get_sse_broker() -> SSEBroker:
    """Return the process-wide :class:`SSEBroker` singleton."""
    global _broker
    if _broker is None:
        _broker = SSEBroker()
    return _broker
