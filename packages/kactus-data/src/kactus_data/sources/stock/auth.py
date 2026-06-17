"""vnstock authentication & rate-limit helpers.

The vnstock paid tier is unlocked via ``vnai.setup_api_key`` — NOT an env var
read by vnstock itself, and NOT ``vnstock.register_user`` (which does not
exist).  The key is read from the registered settings
(``settings.vnstock_api_key`` ← ``KACTUS_VNSTOCK_API_KEY``); when absent vnstock
falls back to the guest tier (~20 requests/min).

``vnai`` is imported lazily inside each function so importing this module never
triggers vnstock's heavy import chain (which also requires ``pytz``).
"""

from __future__ import annotations

from loguru import logger

# Conservative requests/min budget per vnstock tier name, used to size the
# crawl concurrency semaphore.  Mirrors vnstock's published limits.
_TIER_RPM: dict[str, int] = {
    "guest": 20,
    "free": 60,
    "paid": 180,
}
_DEFAULT_RPM = 20


def init_vnstock_auth() -> bool:
    """Authenticate vnstock from settings. Returns ``True`` if a key was applied.

    Idempotent and never raises: an auth failure degrades to the guest tier
    rather than crashing app/scheduler startup.  The key value is never logged.
    """
    from kactus_common.config import settings

    api_key = getattr(settings, "vnstock_api_key", "") or ""
    if not api_key:
        logger.warning(
            "vnstock_api_key not set — running at guest tier (~20 req/min). "
            "Set KACTUS_VNSTOCK_API_KEY to unlock a higher tier."
        )
        return False

    try:
        import vnai

        vnai.setup_api_key(api_key)
        logger.info(f"vnstock authenticated (tier={_safe_tier_name() or 'unknown'})")
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"vnstock auth failed, falling back to guest tier: {exc}")
        return False


def _safe_tier_name() -> str | None:
    """Best-effort vnstock tier name; ``None`` if unavailable. Never raises."""
    try:
        import vnai

        info = vnai.get_tier_info()
        if isinstance(info, dict):
            return info.get("tier") or info.get("name")
        return str(info) if info else None
    except Exception:  # pragma: no cover - defensive
        return None


def vnstock_max_concurrency() -> int:
    """Max concurrent vnstock calls, derived from the active tier.

    Keeps concurrency well under the per-minute budget so the crawler never
    bursts past the rate limit.  Range: 1 (guest) … 8 (paid).
    """
    tier = (_safe_tier_name() or "guest").lower()
    rpm = _TIER_RPM.get(tier, _DEFAULT_RPM)
    return max(1, min(8, rpm // 20))
