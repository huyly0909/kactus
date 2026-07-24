"""Distributed lock — ``SET NX PX`` with a fenced release.

Used to make an operation single-flight across processes (a crawl that must not
run twice, a catalog sync). Deliberately simple: single-instance Redis, no
Redlock. If Redis fails over mid-hold the lock can be lost, so callers must treat
this as an optimisation over a correctness guarantee — the authoritative dedup
for crawls is still the ``CrawlRun`` row in Postgres.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from kactus_common.redis.client import get_redis, namespaced
from loguru import logger

# Release must be compare-and-delete: a plain DEL would let a caller whose lock
# already expired delete the *next* holder's lock.
_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


@asynccontextmanager
async def distributed_lock(
    key: str, *, ttl_secs: int = 60, blocking: bool = False
) -> AsyncIterator[bool]:
    """Hold a named lock for the duration of the block.

    Yields ``True`` if the lock was acquired, ``False`` if someone else holds it.
    The caller decides what "someone else has it" means — usually "skip":

        async with distributed_lock("crawl:stock:quotes", ttl_secs=600) as got:
            if not got:
                return
            ...

    ``ttl_secs`` must exceed the longest plausible run of the guarded block; the
    lock self-expires so a crashed holder cannot wedge the key forever.
    """
    redis = get_redis()
    full_key = namespaced("lock", key)
    token = uuid.uuid4().hex.encode()

    acquired = bool(await redis.set(full_key, token, nx=True, px=ttl_secs * 1000))
    if not acquired and blocking:
        raise RuntimeError(
            f"Lock {key!r} is held and blocking=True is not implemented — "
            "poll at the call site if you need to wait."
        )

    try:
        yield acquired
    finally:
        if acquired:
            try:
                await redis.eval(_RELEASE, 1, full_key, token)
            except (
                Exception
            ) as exc:  # noqa: BLE001 — releasing must not mask the body's error
                logger.warning(f"Failed to release lock {key!r}: {exc}")
