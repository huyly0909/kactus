"""Health check — the one route with no service token.

Compose's ``depends_on: condition: service_healthy`` and any external prober
must be able to reach it without holding the secret. It reveals only whether
the parts are wired, never any data.
"""

from fastapi import APIRouter
from kactus_common.config import settings
from kactus_common.redis.client import redis_health
from kactus_data_plane.runtime import get_runtime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Report the three things that make this service useful."""
    body: dict = {"status": "ok"}

    # DuckDB open? Without it every market read is a 500.
    try:
        get_runtime()
        body["duckdb"] = "ok"
    except Exception:  # noqa: BLE001 — health checks report, they don't propagate
        body["duckdb"] = "uninitialised"
        body["status"] = "degraded"

    # Scheduler running? A data plane that serves reads but never crawls looks
    # healthy from the outside while the data silently goes stale.
    try:
        scheduler = get_runtime().scheduler
        body["scheduler"] = "running" if scheduler is not None else "off"
    except Exception:  # noqa: BLE001
        body["scheduler"] = "off"

    if getattr(settings, "coordination_backend", "memory") == "redis":
        ok = await redis_health()
        body["redis"] = "ok" if ok else "unreachable"
        if not ok:
            # Crawls still run and reads still work; only the SSE nudge to the
            # control plane is lost. Degraded, not down.
            body["status"] = "degraded"

    return body
