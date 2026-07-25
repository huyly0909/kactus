"""Tests for the Redis coordination layer: lock, cache, and the SSE broker.

Backed by ``fakeredis`` rather than a live server so these run in the default
``uv run pytest`` (no Docker). fakeredis implements the actual command
semantics — ``SET NX PX``, key TTL, ``EVAL``, pub/sub — so the behaviour under
test is real; what is faked is the socket.

The broker tests are the important ones. They construct **two brokers over one
shared Redis**, which is the two-uvicorn-workers case: the whole point of the
Redis backend is that a client connected to worker B hears an event published by
worker A.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
import pytest_asyncio
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.redis import cache as cache_mod
from kactus_common.redis import client as client_mod
from kactus_common.redis import lock as lock_mod
from kactus_common.sse import broker as broker_mod
from kactus_common.sse.broker import (
    InProcessSSEBroker,
    RedisSSEBroker,
    get_sse_broker,
    reset_sse_broker,
)


@pytest_asyncio.fixture
async def redis(monkeypatch):
    """One shared fake server; ``get_redis()`` everywhere returns a client on it."""
    register_settings(CommonSettings())
    server = fakeredis.aioredis.FakeRedis()
    for module in (client_mod, cache_mod, lock_mod, broker_mod):
        monkeypatch.setattr(module, "get_redis", lambda: server, raising=False)
    yield server
    await server.flushall()
    await server.aclose()
    reset_sse_broker()
    clear_settings()


# --------------------------------------------------------------------------- #
# Keys are namespaced so one Redis can host several environments
# --------------------------------------------------------------------------- #
def test_namespaced_prefixes_every_key():
    register_settings(CommonSettings(redis_key_prefix="kactus-stag"))
    assert client_mod.namespaced("cache", "market", "gold") == (
        "kactus-stag:cache:market:gold"
    )
    clear_settings()


# --------------------------------------------------------------------------- #
# distributed_lock
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_lock_is_exclusive_then_released(redis):
    async with lock_mod.distributed_lock("crawl:stock", ttl_secs=30) as first:
        assert first is True
        # A second holder while the first is inside the block: denied.
        async with lock_mod.distributed_lock("crawl:stock", ttl_secs=30) as second:
            assert second is False

    # Released on exit, so the next caller gets it.
    async with lock_mod.distributed_lock("crawl:stock", ttl_secs=30) as third:
        assert third is True


@pytest.mark.asyncio
async def test_lock_release_does_not_delete_another_holders_key(redis):
    """The classic lock bug: an expired holder must not free the next one's lock.

    Simulated by letting the lock expire mid-block and having someone else take
    it — the first holder's release must be a no-op, not a DEL.
    """
    key = client_mod.namespaced("lock", "short")
    async with lock_mod.distributed_lock("short", ttl_secs=30) as got:
        assert got
        await redis.delete(key)  # first holder's lock expires
        await redis.set(key, b"someone-elses-token")  # second holder takes it

    # Compare-and-delete: the token no longer matches, so the key survives.
    assert await redis.get(key) == b"someone-elses-token"


@pytest.mark.asyncio
async def test_lock_expires_on_its_own(redis):
    """A crashed holder must not wedge the key — the TTL is the safety net."""
    key = client_mod.namespaced("lock", "ttl-probe")
    async with lock_mod.distributed_lock("ttl-probe", ttl_secs=5):
        ttl = await redis.pttl(key)
        assert 0 < ttl <= 5000


# --------------------------------------------------------------------------- #
# cache
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_cache_round_trip_and_delete(redis):
    await cache_mod.cache_set("market", "gold", {"sjc": 1_000}, ttl_secs=60)
    assert await cache_mod.cache_get("market", "gold") == {"sjc": 1_000}

    await cache_mod.cache_delete("market", "gold")
    assert await cache_mod.cache_get("market", "gold") is None


@pytest.mark.asyncio
async def test_cache_miss_returns_none(redis):
    assert await cache_mod.cache_get("market", "never-written") is None


@pytest.mark.asyncio
async def test_cache_set_always_carries_a_ttl(redis):
    """No immortal keys — an entry with no expiry would outlive its source data."""
    await cache_mod.cache_set("market", "gold", {"x": 1}, ttl_secs=42)
    ttl = await redis.ttl(client_mod.namespaced("cache", "market", "gold"))
    assert 0 < ttl <= 42


@pytest.mark.asyncio
async def test_cache_clear_namespace_leaves_other_namespaces(redis):
    await cache_mod.cache_set("market", "a", 1, ttl_secs=60)
    await cache_mod.cache_set("market", "b", 2, ttl_secs=60)
    await cache_mod.cache_set("portfolio", "c", 3, ttl_secs=60)

    removed = await cache_mod.cache_clear_namespace("market")
    assert removed == 2
    assert await cache_mod.cache_get("market", "a") is None
    assert await cache_mod.cache_get("portfolio", "c") == 3


@pytest.mark.asyncio
async def test_cache_read_degrades_instead_of_raising(redis, monkeypatch):
    """A Redis outage must not turn a cached read into a 500."""

    async def _boom(*a, **k):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(redis, "get", _boom)
    assert await cache_mod.cache_get("market", "gold") is None


# --------------------------------------------------------------------------- #
# SSE broker — backend selection
# --------------------------------------------------------------------------- #
def test_broker_defaults_to_in_process():
    register_settings(CommonSettings())
    reset_sse_broker()
    assert isinstance(get_sse_broker(), InProcessSSEBroker)
    reset_sse_broker()
    clear_settings()


def test_broker_honours_redis_setting():
    register_settings(CommonSettings(coordination_backend="redis"))
    reset_sse_broker()
    assert isinstance(get_sse_broker(), RedisSSEBroker)
    reset_sse_broker()
    clear_settings()


# --------------------------------------------------------------------------- #
# SSE broker — fan-out
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_in_process_broker_fans_out_to_its_subscribers():
    broker = InProcessSSEBroker()
    queue = await broker.subscribe()
    await broker.publish({"kind": "quotes"})
    assert queue.get_nowait() == {"kind": "quotes"}


@pytest.mark.asyncio
async def test_in_process_broker_drops_for_a_stalled_client():
    """A client that stopped reading loses messages; it must not block the rest."""
    broker = InProcessSSEBroker(max_queue=1)
    stalled = await broker.subscribe()
    healthy = await broker.subscribe()
    stalled.put_nowait({"filler": True})  # stalled client's queue is now full

    await broker.publish({"kind": "quotes"})

    assert healthy.get_nowait() == {"kind": "quotes"}
    assert stalled.get_nowait() == {"filler": True}  # the nudge was dropped
    assert stalled.empty()


@pytest.mark.asyncio
async def test_redis_broker_delivers_across_two_workers(redis):
    """The reason this backend exists: worker A publishes, worker B's client hears.

    With the in-process broker this assertion is impossible to satisfy — which is
    exactly the production bug of running --workers 4 with a per-process broker.
    """
    worker_a = RedisSSEBroker()
    worker_b = RedisSSEBroker()
    queue_b = await worker_b.subscribe()

    try:
        await worker_a.publish({"asset_type": "STOCK", "kind": "quotes"})
        message = await asyncio.wait_for(queue_b.get(), timeout=5)
        assert message == {"asset_type": "STOCK", "kind": "quotes"}
    finally:
        await worker_a.close()
        await worker_b.close()


@pytest.mark.asyncio
async def test_redis_broker_delivers_to_the_publishing_worker_too(redis):
    """The publisher is not special — it receives its own event back via Redis.

    Guards against a 'publish locally *and* to Redis' regression, which would
    deliver twice to the publishing worker's own clients.
    """
    broker = RedisSSEBroker()
    queue = await broker.subscribe()

    try:
        await broker.publish({"kind": "news"})
        assert await asyncio.wait_for(queue.get(), timeout=5) == {"kind": "news"}
        # …exactly once.
        await asyncio.sleep(0.05)
        assert queue.empty()
    finally:
        await broker.close()
