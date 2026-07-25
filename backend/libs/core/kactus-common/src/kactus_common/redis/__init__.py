"""Redis coordination primitives.

Redis is used here for **coordination between processes**, never as a job queue
and never as a source of truth:

* ``client``  — the process-wide async pool + ``namespaced()`` key builder.
* ``lock``    — ``distributed_lock()``, single-flight across workers.
* ``cache``   — namespaced get/set/delete, TTL mandatory.

What deliberately does *not* live here: audit rows (Postgres), inter-service
commands (HTTP), and scheduled jobs (APScheduler in the owning process).
"""

from kactus_common.redis.cache import (
    cache_clear_namespace,
    cache_delete,
    cache_get,
    cache_set,
)
from kactus_common.redis.client import close_redis, get_redis, namespaced, redis_health
from kactus_common.redis.lock import distributed_lock

__all__ = [
    "get_redis",
    "close_redis",
    "redis_health",
    "namespaced",
    "distributed_lock",
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_clear_namespace",
]
