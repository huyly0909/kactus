"""SSE broker — fan-out of server-side events to connected browser clients.

Two backends behind one interface, chosen by ``settings.coordination_backend``:

* ``InProcessSSEBroker`` — subscribers live in this process only. Correct at
  ``--workers 1``; with N workers a client only hears events published by the
  worker its connection happens to have landed on.
* ``RedisSSEBroker`` — ``publish()`` goes to a Redis channel and *every* worker's
  listener fans it back out to its own local subscribers. The worker that
  published is not special: it receives its own message back through Redis, so
  there is exactly one delivery path and no double-send.

Subscribers always get a **bounded local queue** in both backends. A stalled
client drops messages instead of back-pressuring the publisher or growing
without limit — market nudges are refresh hints, and a client that missed one
refetches on the next.

This is the Loại A pattern: never route to "the worker holding the connection".
Publish to Redis; whichever worker holds a given connection picks it up itself.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import orjson
from kactus_common.config import settings
from loguru import logger

_CHANNEL = "sse:market"


class SSEBroker(ABC):
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

    @abstractmethod
    async def publish(self, message: dict) -> None:
        """Deliver ``message`` to every subscriber, in this process or beyond."""

    async def close(self) -> None:
        """Release backend resources — called from the app lifespan shutdown."""

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def _fan_out_local(self, message: dict) -> None:
        """Push to this process's queues, dropping for any client that stalled."""
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full — dropping message")


class InProcessSSEBroker(SSEBroker):
    """Single-process fan-out. The default, and what the tests run against."""

    async def publish(self, message: dict) -> None:
        self._fan_out_local(message)


class RedisSSEBroker(SSEBroker):
    """Cross-process fan-out over Redis pub/sub.

    One background listener per process, started lazily on the first
    ``subscribe()`` — an event loop has to exist, and a worker with no SSE
    clients has no reason to hold a subscription open.

    Pub/sub, not Streams, is the right fit here: these are refresh nudges that a
    client can miss without harm (it refetches). Anything that must *not* be lost
    — notification delivery — belongs on a Stream with a consumer group instead.
    """

    def __init__(self, max_queue: int = 100) -> None:
        super().__init__(max_queue=max_queue)
        self._listener: asyncio.Task | None = None
        self._ready: asyncio.Event = asyncio.Event()

    async def subscribe(self) -> asyncio.Queue:
        await self._ensure_listener()
        return await super().subscribe()

    async def publish(self, message: dict) -> None:
        # Deliberately no local fan-out here: the message comes back to this
        # process through the listener like it does to every other worker.
        from kactus_common.redis.client import get_redis, namespaced

        await get_redis().publish(namespaced(_CHANNEL), orjson.dumps(message))

    async def close(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except asyncio.CancelledError:
                pass
            self._listener = None
        self._ready.clear()

    async def _ensure_listener(self) -> None:
        if self._listener is None or self._listener.done():
            self._ready.clear()
            self._listener = asyncio.create_task(self._listen())
            # Wait for SUBSCRIBE to be acknowledged before the caller can publish,
            # otherwise the first event races the subscription and is lost.
            await self._ready.wait()

    async def _listen(self) -> None:
        from kactus_common.redis.client import get_redis, namespaced

        pubsub = get_redis().pubsub()
        channel = namespaced(_CHANNEL)
        await pubsub.subscribe(channel)
        self._ready.set()
        logger.info(f"SSE listener subscribed to Redis channel {channel}")
        try:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    self._fan_out_local(orjson.loads(raw["data"]))
                except orjson.JSONDecodeError:
                    logger.warning("Dropping malformed SSE payload from Redis")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — a dead listener must be visible
            logger.error(f"SSE Redis listener stopped: {exc}")
        finally:
            await pubsub.aclose()


# --------------------------------------------------------------------------- #
# Module-level singleton — one broker per process.
# --------------------------------------------------------------------------- #
_broker: SSEBroker | None = None


def get_sse_broker() -> SSEBroker:
    """Return the process-wide broker, per ``settings.coordination_backend``.

    Resolved once and cached: switching backends means a restart, which is the
    honest behaviour — half the workers on Redis and half in memory would be a
    very confusing thing to debug.
    """
    global _broker
    if _broker is None:
        backend = getattr(settings, "coordination_backend", "memory")
        _broker = RedisSSEBroker() if backend == "redis" else InProcessSSEBroker()
        logger.info(f"SSE broker backend: {backend}")
    return _broker


def reset_sse_broker() -> None:
    """Drop the cached broker (tests, and lifespan shutdown)."""
    global _broker
    _broker = None
