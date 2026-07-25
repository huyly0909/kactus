"""Delivery queue — Redis **Streams**, deliberately not pub/sub.

``Notifier.send_event`` runs the transport inline with bounded retry (up to
``notification_max_send_attempts`` with exponential backoff).  Called straight
from ``POST /{channel_id}/send`` that is tens of seconds of request time when the
far side is lagging, for a result the caller cannot act on anyway.  This module
is the buffer: the request ``XADD``s and returns; a consumer sends.

**Streams, not pub/sub.**  ``PUBLISH`` has no memory — a consumer restarting in
the same second a message is published loses it permanently, and nothing anywhere
records that it happened.  Losing a user's price alert is a real failure, so
delivery goes through a consumer group: entries stay *pending* until they are
``XACK``-ed, and a consumer that dies mid-send leaves its entries claimable by
the next one.  The SSE nudge in ``kactus_common.sse`` is the opposite case and
correctly uses pub/sub — the browser refetches, so a dropped nudge costs nothing.

**Ack semantics** (the whole reason to use Streams):

- handler returns  → ``XACK``.  Done, forget it.
- handler *raises* → **no ack**.  The entry stays pending and :meth:`
  NotificationQueueConsumer.reclaim_stale` re-delivers it once it has been idle
  long enough.  Raising therefore means *"this was not handled"* — a crash, a
  dead database — not *"the send failed"*.  A send that failed and was written
  to ``NotificationLog`` **is** handled; the handler must swallow it, otherwise
  one permanently-broken channel re-delivers forever.
- re-delivered past ``notification_queue_max_deliveries`` → acked and logged at
  ERROR.  Without that cap a payload that crashes the handler deterministically
  is an infinite loop.

The stream is capped (``notification_queue_maxlen``, approximate trimming): it is
a buffer, not the audit trail.  ``NotificationLog`` in Postgres is the record of
what was sent, and it stays that way — Redis can be flushed or lost on failover.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from kactus_common.config import settings
from kactus_common.redis.client import get_redis, namespaced
from loguru import logger
from redis.exceptions import ResponseError

from .const import NotificationTrigger
from .schema import NotificationEvent

#: One group for every sender.  Members of a consumer group *share* the stream —
#: each entry goes to exactly one consumer — which is what makes it a work queue
#: rather than a broadcast.  Adding a second kind of consumer later (a singleton
#: connection holder, say) means a second *group*, not a second stream.
CONSUMER_GROUP = "notifiers"


def stream_key() -> str:
    """The stream's Redis key, namespaced so environments cannot collide."""
    return namespaced("notify", "stream")


@dataclass(frozen=True)
class QueuedNotification:
    """One decoded stream entry, ready to hand to a handler."""

    message_id: str
    channel_id: int
    owner_id: int
    event: NotificationEvent
    trigger: NotificationTrigger


#: A handler takes one entry and either returns (ack) or raises (replay).
NotificationHandler = Callable[[QueuedNotification], Awaitable[None]]


def _as_str(value: bytes | str) -> str:
    """Redis is opened with ``decode_responses=False``; decode at this boundary."""
    return value.decode() if isinstance(value, bytes) else value


async def _ensure_group(redis) -> None:
    """Create the consumer group if it is not there yet (idempotent).

    Starting at ``id="0"`` rather than ``"$"``: a group created at ``$`` skips
    everything already in the stream, so a consumer booting after a producer
    would silently drop the backlog.  ``mkstream`` covers the reverse order —
    a consumer that starts before the first send.
    """
    try:
        await redis.xgroup_create(stream_key(), CONSUMER_GROUP, id="0", mkstream=True)
    except ResponseError as exc:  # noqa: PERF203 — one-shot, not a loop
        if "BUSYGROUP" not in str(exc):
            raise


async def enqueue(
    *,
    channel_id: int,
    owner_id: int,
    event: NotificationEvent,
    trigger: NotificationTrigger = NotificationTrigger.MANUAL,
) -> str:
    """Append one send to the stream and return its message id.

    ``owner_id`` rides along so the consumer can re-assert ownership when it
    loads the channel: the entry may be handled minutes later, in a different
    process, with no request and no ``request.state.user`` to check against.
    """
    redis = get_redis()
    await _ensure_group(redis)
    message_id = await redis.xadd(
        stream_key(),
        {
            "channel_id": str(channel_id),
            "owner_id": str(owner_id),
            "trigger": trigger.value,
            "event": event.model_dump_json(),
        },
        maxlen=settings.notification_queue_maxlen,
        approximate=True,
    )
    return _as_str(message_id)


def _parse(message_id: str, fields: dict) -> QueuedNotification:
    """Decode one raw stream entry. Raises if the payload is malformed."""
    decoded = {_as_str(k): _as_str(v) for k, v in fields.items()}
    return QueuedNotification(
        message_id=message_id,
        channel_id=int(decoded["channel_id"]),
        owner_id=int(decoded["owner_id"]),
        event=NotificationEvent.model_validate_json(decoded["event"]),
        trigger=NotificationTrigger(decoded["trigger"]),
    )


class NotificationQueueConsumer:
    """Reads the stream and hands entries to ``handler``.

    Runs as one background task per process.  Several processes may run one each
    — that is the point of a consumer group, and it is why this lives in
    kactus-fin (multi-worker) rather than in the single-replica data plane:
    ``consumer_name`` distinguishes them, entries are distributed rather than
    duplicated, and a worker dying leaves its pending entries for the others.
    """

    def __init__(
        self,
        handler: NotificationHandler,
        *,
        consumer_name: str,
        batch: int | None = None,
        block_ms: int | None = None,
        claim_idle_ms: int | None = None,
        max_deliveries: int | None = None,
        error_backoff: float = 1.0,
    ) -> None:
        self._handler = handler
        self.consumer_name = consumer_name
        self.batch = batch or settings.notification_queue_batch
        self.block_ms = (
            block_ms if block_ms is not None else settings.notification_queue_block_ms
        )
        self.claim_idle_ms = (
            claim_idle_ms
            if claim_idle_ms is not None
            else settings.notification_queue_claim_idle_ms
        )
        self.max_deliveries = (
            max_deliveries or settings.notification_queue_max_deliveries
        )
        self._error_backoff = error_backoff
        self._task: asyncio.Task | None = None

    # ----------------------------------------------------------------- #
    # Lifecycle
    # ----------------------------------------------------------------- #
    async def start(self) -> None:
        """Spawn the read loop. Idempotent."""
        if self._task is not None:
            return
        await _ensure_group(get_redis())
        self._task = asyncio.create_task(
            self._run(), name=f"notify-consumer-{self.consumer_name}"
        )
        logger.info(f"Notification queue consumer {self.consumer_name} started")

    async def stop(self) -> None:
        """Cancel the read loop and wait for it to unwind.

        Entries this consumer had read but not acked stay pending on purpose —
        :meth:`reclaim_stale` on whichever worker comes back picks them up.
        """
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info(f"Notification queue consumer {self.consumer_name} stopped")

    async def _run(self) -> None:
        while True:
            try:
                await self.reclaim_stale()
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — the loop must outlive Redis
                logger.error(f"Notification queue consumer loop error: {exc}")
                await asyncio.sleep(self._error_backoff)

    # ----------------------------------------------------------------- #
    # One round — public so tests can drive the consumer without a task
    # ----------------------------------------------------------------- #
    async def run_once(self) -> int:
        """Read up to ``batch`` new entries and dispatch them. Returns acks."""
        redis = get_redis()
        await _ensure_group(redis)
        response = await redis.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=self.consumer_name,
            streams={stream_key(): ">"},
            count=self.batch,
            block=self.block_ms or None,
        )
        handled = 0
        for _stream, entries in response or []:
            for message_id, fields in entries:
                handled += await self._dispatch(redis, message_id, fields)
        return handled

    async def reclaim_stale(self) -> int:
        """Re-deliver entries another consumer read but never acked.

        This is the replay path: a worker killed mid-send leaves its entries
        pending forever otherwise.  ``times_delivered`` is checked *before*
        claiming so a poison entry is dropped rather than re-run.
        """
        redis = get_redis()
        await _ensure_group(redis)
        pending = await redis.xpending_range(
            stream_key(), CONSUMER_GROUP, min="-", max="+", count=self.batch
        )
        handled = 0
        for entry in pending or []:
            if entry["time_since_delivered"] < self.claim_idle_ms:
                continue  # still in flight on a live consumer
            message_id = _as_str(entry["message_id"])
            if entry["times_delivered"] >= self.max_deliveries:
                logger.error(
                    f"Dropping notification {message_id} after "
                    f"{entry['times_delivered']} deliveries — it keeps failing "
                    f"the handler. Check NotificationLog for the channel."
                )
                await redis.xack(stream_key(), CONSUMER_GROUP, message_id)
                continue
            claimed = await redis.xclaim(
                stream_key(),
                CONSUMER_GROUP,
                self.consumer_name,
                min_idle_time=self.claim_idle_ms,
                message_ids=[message_id],
            )
            for claimed_id, fields in claimed or []:
                handled += await self._dispatch(redis, claimed_id, fields)
        return handled

    async def _dispatch(self, redis, message_id, fields) -> int:
        mid = _as_str(message_id)
        try:
            queued = _parse(mid, fields)
        except Exception as exc:  # noqa: BLE001
            # Acked on purpose: re-delivering a payload that cannot be decoded
            # produces the same failure forever, and the entry would pin the
            # group's pending list for as long as the stream lives.
            logger.error(f"Dropping unparseable notification entry {mid}: {exc}")
            await redis.xack(stream_key(), CONSUMER_GROUP, mid)
            return 0

        try:
            await self._handler(queued)
        except Exception as exc:  # noqa: BLE001
            # NOT acked — see the module docstring. This branch is for handlers
            # that blew up, not for sends that failed and were logged.
            logger.error(
                f"Notification {mid} left pending for replay "
                f"(channel {queued.channel_id}): {exc}"
            )
            return 0

        await redis.xack(stream_key(), CONSUMER_GROUP, mid)
        return 1
