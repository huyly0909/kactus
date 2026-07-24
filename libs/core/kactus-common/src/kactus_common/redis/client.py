"""Redis connection pool — one per process, published like ``olap.py`` does.

``redis.asyncio`` ships in redis-py itself (aioredis was merged in 4.2), so there
is no second client library here.

The pool is created lazily on first use rather than at import: ``settings`` is
only registered once the app boots, and a CLI command that never touches Redis
should not open a connection to it.
"""

from __future__ import annotations

from kactus_common.config import settings
from redis.asyncio import ConnectionPool, Redis

_pool: ConnectionPool | None = None
_client: Redis | None = None


def get_redis() -> Redis:
    """Return the process-wide async Redis client.

    Decoding is left **off** (``decode_responses=False``): the pub/sub payloads
    and the encrypted session blobs are bytes, and callers that want text decode
    at their own boundary.
    """
    global _pool, _client
    if _client is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=False,
            health_check_interval=30,
        )
        _client = Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    """Close the pool — call from the app lifespan's shutdown half."""
    global _pool, _client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


async def redis_health() -> bool:
    """``True`` if Redis answers PING. Never raises — it feeds /health."""
    try:
        return bool(await get_redis().ping())
    except Exception:  # noqa: BLE001 — health checks report, they don't propagate
        return False


def namespaced(*parts: str) -> str:
    """Build a key under ``settings.redis_key_prefix``.

    Every key this codebase writes goes through here, so one Redis instance can
    host several environments without them colliding.
    """
    return ":".join((settings.redis_key_prefix, *parts))
