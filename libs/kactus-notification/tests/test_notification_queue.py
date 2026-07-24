"""The Redis Streams delivery queue.

Backed by ``fakeredis`` (same arrangement as the coordination-layer suite), which
implements real stream semantics — consumer groups, the pending-entries list,
``XACK``, ``XCLAIM``, ``times_delivered`` — so what is faked is the socket, not
the behaviour under test.

The tests that matter are the ones about **not** losing a message: a consumer
that dies mid-handle must leave the entry claimable, which is the entire reason
this is Streams and not pub/sub.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest
import pytest_asyncio
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.redis import client as client_mod
from kactus_notification import queue as queue_mod
from kactus_notification.config import NotificationSettings
from kactus_notification.const import NotificationLevel, NotificationTrigger
from kactus_notification.queue import (
    CONSUMER_GROUP,
    NotificationQueueConsumer,
    enqueue,
    stream_key,
)
from kactus_notification.schema import NotificationEvent


class _Settings(CommonSettings, NotificationSettings):
    """The mixin merge kactus-fin does, minus everything unrelated."""


@pytest_asyncio.fixture
async def redis(monkeypatch):
    register_settings(_Settings())
    server = fakeredis.aioredis.FakeRedis()
    for module in (client_mod, queue_mod):
        monkeypatch.setattr(module, "get_redis", lambda: server, raising=False)
    yield server
    await server.flushall()
    await server.aclose()
    clear_settings()


def _event(title: str = "FPT hit 100") -> NotificationEvent:
    return NotificationEvent(
        title=title,
        body="Target price reached",
        level=NotificationLevel.INFO,
        fields=[("symbol", "FPT"), ("price", "100000")],
        url="https://kactus.test/actions/abc",
    )


async def _record(sink: list, queued) -> None:
    sink.append(queued)


def _collect(sink: list):
    """An async handler that appends — handlers are awaited, so ``list.append``
    on its own is a ``TypeError`` the consumer would swallow as a crash."""

    async def handler(queued):
        sink.append(queued)

    return handler


def _consumer(handler, **kwargs) -> NotificationQueueConsumer:
    """A consumer that never blocks — tests drive ``run_once`` by hand."""
    kwargs.setdefault("block_ms", 0)
    kwargs.setdefault("claim_idle_ms", 0)
    return NotificationQueueConsumer(handler, consumer_name="test-1", **kwargs)


# --------------------------------------------------------------------------- #
# enqueue
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_enqueue_writes_a_namespaced_stream_entry(redis):
    message_id = await enqueue(channel_id=7, owner_id=42, event=_event())

    assert message_id  # "<ms>-<seq>"
    assert stream_key() == "kactus:notify:stream"
    assert await redis.xlen(stream_key()) == 1


@pytest.mark.asyncio
async def test_round_trip_preserves_the_whole_event(redis):
    """The event crosses a JSON boundary, so every field has to survive it."""
    seen: list = []
    await enqueue(
        channel_id=7,
        owner_id=42,
        event=_event(),
        trigger=NotificationTrigger.EVENT,
    )
    await _consumer(_collect(seen)).run_once()

    (queued,) = seen
    assert queued.channel_id == 7
    assert queued.owner_id == 42
    assert queued.trigger is NotificationTrigger.EVENT
    assert queued.event.title == "FPT hit 100"
    assert queued.event.fields == [("symbol", "FPT"), ("price", "100000")]
    # The actionable link is the payload Phase 3.3 rides on — it must not be
    # dropped somewhere in the middle.
    assert queued.event.url == "https://kactus.test/actions/abc"


# --------------------------------------------------------------------------- #
# Ack semantics — the reason this is Streams
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_handled_entry_is_acked_and_not_redelivered(redis):
    calls: list = []

    async def handler(queued):
        calls.append(queued.message_id)

    consumer = _consumer(handler)
    await enqueue(channel_id=1, owner_id=1, event=_event())

    assert await consumer.run_once() == 1
    assert await consumer.run_once() == 0  # nothing new
    assert await consumer.reclaim_stale() == 0  # and nothing pending
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_crashed_handler_leaves_the_entry_pending(redis):
    """A handler that raises must not ack — that is the replay guarantee.

    This is the case pub/sub cannot express: with ``PUBLISH`` the message is
    gone the instant it is delivered, whether or not the consumer survived it.
    """

    async def handler(queued):
        raise RuntimeError("database is down")

    consumer = _consumer(handler)
    await enqueue(channel_id=1, owner_id=1, event=_event())
    assert await consumer.run_once() == 0

    pending = await redis.xpending_range(
        stream_key(), CONSUMER_GROUP, min="-", max="+", count=10
    )
    assert len(pending) == 1


@pytest.mark.asyncio
async def test_killed_consumer_is_replayed_by_the_next_one(redis):
    """Kill a consumer mid-handle, start another → the message is processed.

    The plan's verification bar for this phase, in one test.
    """
    delivered: list = []

    async def dies(queued):
        raise RuntimeError("SIGKILL")

    async def survives(queued):
        delivered.append(queued.event.title)

    # First worker reads it and dies before acking.
    await enqueue(channel_id=1, owner_id=1, event=_event("only alert"))
    await NotificationQueueConsumer(
        dies, consumer_name="worker-a", block_ms=0, claim_idle_ms=0
    ).run_once()
    assert delivered == []

    # Second worker starts up and claims what the first left behind.
    replacement = NotificationQueueConsumer(
        survives, consumer_name="worker-b", block_ms=0, claim_idle_ms=0
    )
    assert await replacement.run_once() == 0  # ">" only yields *new* entries
    assert await replacement.reclaim_stale() == 1

    assert delivered == ["only alert"]


@pytest.mark.asyncio
async def test_poison_entry_is_dropped_after_max_deliveries(redis):
    """A deterministically-crashing payload must not loop forever."""
    attempts = 0

    async def always_fails(queued):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("bad payload")

    consumer = _consumer(always_fails, max_deliveries=3)
    await enqueue(channel_id=1, owner_id=1, event=_event())
    await consumer.run_once()  # delivery 1

    for _ in range(5):
        await consumer.reclaim_stale()

    assert attempts == 3  # then acked and dropped, not retried forever
    pending = await redis.xpending_range(
        stream_key(), CONSUMER_GROUP, min="-", max="+", count=10
    )
    assert pending == []


@pytest.mark.asyncio
async def test_unparseable_entry_is_acked_not_retried(redis):
    """Redelivering a payload that cannot be decoded produces the same failure.

    Acking it is the only way it ever leaves the pending list.
    """
    called = False

    async def handler(queued):
        nonlocal called
        called = True

    await redis.xgroup_create(stream_key(), CONSUMER_GROUP, id="0", mkstream=True)
    await redis.xadd(stream_key(), {"channel_id": "not-an-int"})

    consumer = _consumer(handler)
    assert await consumer.run_once() == 0
    assert called is False
    assert (
        await redis.xpending_range(
            stream_key(), CONSUMER_GROUP, min="-", max="+", count=10
        )
        == []
    )


@pytest.mark.asyncio
async def test_in_flight_entry_is_not_stolen_by_a_second_consumer(redis):
    """``claim_idle_ms`` is what stops two workers sending the same alert.

    With a live consumer still working on an entry, a sibling's reclaim pass
    must leave it alone — otherwise scaling kactus-fin to 4 workers would
    double-send every slow notification.
    """

    async def hangs(queued):
        raise RuntimeError("still working")

    await enqueue(channel_id=1, owner_id=1, event=_event())
    await NotificationQueueConsumer(
        hangs, consumer_name="worker-a", block_ms=0, claim_idle_ms=0
    ).run_once()

    sibling = NotificationQueueConsumer(
        hangs, consumer_name="worker-b", block_ms=0, claim_idle_ms=60_000
    )
    assert await sibling.reclaim_stale() == 0


# --------------------------------------------------------------------------- #
# Group placement
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_group_starts_at_zero_so_a_late_consumer_sees_the_backlog(redis):
    """A group created at ``$`` would skip everything already enqueued."""
    seen: list = []

    # Producer runs first; no consumer exists yet.
    await enqueue(channel_id=1, owner_id=1, event=_event("earlier"))
    await enqueue(channel_id=1, owner_id=1, event=_event("later"))

    assert await _consumer(_collect(seen)).run_once() == 2
    assert [q.event.title for q in seen] == ["earlier", "later"]


@pytest.mark.asyncio
async def test_group_members_share_the_work_rather_than_duplicating_it(redis):
    """Two consumers in one group = a work queue, not a broadcast.

    This is what makes running the consumer on every kactus-fin worker correct
    instead of a four-times-every-alert bug.
    """
    a_saw: list = []
    b_saw: list = []

    for i in range(4):
        await enqueue(channel_id=1, owner_id=1, event=_event(f"alert-{i}"))

    a = NotificationQueueConsumer(
        _collect(a_saw), consumer_name="a", block_ms=0, batch=2
    )
    b = NotificationQueueConsumer(
        _collect(b_saw), consumer_name="b", block_ms=0, batch=2
    )
    await a.run_once()
    await b.run_once()

    titles = [q.event.title for q in a_saw + b_saw]
    assert sorted(titles) == ["alert-0", "alert-1", "alert-2", "alert-3"]
    assert len(a_saw) == 2 and len(b_saw) == 2


# --------------------------------------------------------------------------- #
# start/stop
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_unwinds(redis):
    consumer = _consumer(_collect([]), block_ms=10)
    await consumer.start()
    task = consumer._task
    await consumer.start()
    assert consumer._task is task  # not a second loop

    await consumer.stop()
    assert consumer._task is None
    await consumer.stop()  # no-op, does not raise
