"""Namespaced TTL cache over Redis.

Values are JSON (orjson, same as everywhere else in the codebase) — this is a
cache for derived data, not a place to stash Python objects.

Nothing here is a source of truth. Redis can be flushed, evicted under
``maxmemory``, or lost in a failover; every read must be reconstructible from
Postgres or DuckDB.
"""

from __future__ import annotations

from typing import Any

import orjson
from kactus_common.redis.client import get_redis, namespaced
from loguru import logger


async def cache_get(namespace: str, key: str) -> Any | None:
    """Return the cached value, or ``None`` on a miss / unreachable Redis."""
    try:
        raw = await get_redis().get(namespaced("cache", namespace, key))
    except Exception as exc:  # noqa: BLE001 — a cache outage degrades, never fails
        logger.warning(f"Cache read failed for {namespace}:{key}: {exc}")
        return None
    return orjson.loads(raw) if raw is not None else None


async def cache_set(namespace: str, key: str, value: Any, *, ttl_secs: int) -> None:
    """Store ``value`` under a TTL. A TTL is mandatory — no immortal keys."""
    try:
        await get_redis().set(
            namespaced("cache", namespace, key), orjson.dumps(value), ex=ttl_secs
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cache write failed for {namespace}:{key}: {exc}")


async def cache_delete(namespace: str, key: str) -> None:
    """Drop one key (used on write-through invalidation)."""
    try:
        await get_redis().delete(namespaced("cache", namespace, key))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cache delete failed for {namespace}:{key}: {exc}")


async def cache_clear_namespace(namespace: str) -> int:
    """Delete every key in ``namespace``; returns how many were removed.

    Uses ``SCAN``, not ``KEYS`` — ``KEYS`` blocks the whole server for the length
    of the scan, which on a shared Redis is an outage.
    """
    redis = get_redis()
    pattern = namespaced("cache", namespace, "*")
    removed = 0
    try:
        async for key in redis.scan_iter(match=pattern, count=500):
            removed += await redis.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Cache clear failed for {namespace}: {exc}")
    return removed
