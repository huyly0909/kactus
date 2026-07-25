from fastapi import APIRouter
from kactus_common.config import settings
from kactus_common.redis.client import redis_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Redis is reported only when the deployment actually depends on it. On the
    ``memory`` backend an unreachable Redis is not a fault, and flagging it as
    one would train operators to ignore this endpoint.
    """
    body: dict = {"status": "ok"}

    if getattr(settings, "coordination_backend", "memory") == "redis":
        ok = await redis_health()
        body["redis"] = "ok" if ok else "unreachable"
        if not ok:
            # SSE fan-out and Zalo QR login are both broken in this state, but
            # ordinary requests still work — "degraded", not a hard failure.
            body["status"] = "degraded"

    return body
