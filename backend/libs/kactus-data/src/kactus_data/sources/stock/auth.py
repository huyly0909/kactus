"""vnstock authentication & rate-limit helpers.

The vnstock paid tier is unlocked via ``vnai.setup_api_key`` — NOT an env var
read by vnstock itself, and NOT ``vnstock.register_user`` (which does not
exist).  The key is read from the registered settings
(``settings.vnstock_api_key`` ← ``KACTUS_VNSTOCK_API_KEY``); when absent vnstock
falls back to the guest tier (~20 requests/min).

Tier detection uses ``vnai.get_user_tier()`` — the working endpoint.  (Do NOT
use ``vnai.get_tier_info()``: in the installed vnai it imports the nonexistent
``vnai.beam.quota_endpoint`` module and always fails, which is why logs used to
say ``tier=unknown``.)  Paid tiers (bronze/silver/golden/diamond) are only
recognised when the sponsor-licensed ``vnii`` package is installed; a plain API
key resolves to ``free`` (60 req/min).  ``KACTUS_VNSTOCK_RPM_OVERRIDE`` lets an
admin pin the budget when detection cannot see the real tier.

``vnai`` is imported lazily inside each function so importing this module never
triggers vnstock's heavy import chain (which also requires ``pytz``).
"""

from __future__ import annotations

from loguru import logger

# Requests/min per vnai tier name — mirrors ``Authenticator.TIER_LIMITS`` in
# vnai (guest/free plus the sponsor tiers).  Used only as the static fallback
# when ``vnai.get_user_tier()`` is unavailable.
_TIER_RPM: dict[str, int] = {
    "guest": 20,
    "community": 60,
    "free": 60,
    "bronze": 180,
    "silver": 300,
    "golden": 500,
    "diamond": 600,
}
_DEFAULT_RPM = 20
# rpm assumed when a key authenticated but vnstock won't name the tier; the
# banner advertises 60 req/min for the Community key.
_AUTHED_RPM = 60

# Set True by ``init_vnstock_auth`` when a key is successfully applied, so the
# budget sizing can assume a real tier even if detection fails.
_AUTHENTICATED = False

#: Fraction of the advertised budget we actually spend — vnai counts on its own
#: clock, so pacing at 100% still trips the guard on boundary effects.
_RPM_SAFETY = 0.8


def init_vnstock_auth() -> bool:
    """Authenticate vnstock from settings. Returns ``True`` if a key was applied.

    Idempotent and never raises: an auth failure degrades to the guest tier
    rather than crashing app/scheduler startup.  The key value is never logged.
    Always logs the active tier + budget so the startup log answers "free or
    paid?" at a glance.
    """
    global _AUTHENTICATED
    from kactus_common.config import settings

    api_key = getattr(settings, "vnstock_api_key", "") or ""
    applied = False
    if not api_key:
        logger.warning(
            "vnstock_api_key not set — running at guest tier (~20 req/min). "
            "Set KACTUS_VNSTOCK_API_KEY to unlock a higher tier."
        )
    else:
        try:
            import vnai

            vnai.setup_api_key(api_key)
            _AUTHENTICATED = True
            applied = True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"vnstock auth failed, falling back to guest tier: {exc}")

    info = _tier_info()
    rpm, rpm_source = _resolve_rpm(info)
    per_hour = (info or {}).get("limits", {}).get("per_hour")
    tier = _tier_name_from(info) or ("free" if _AUTHENTICATED else "guest")
    logger.info(
        f"vnstock tier={tier} budget={rpm} req/min"
        + (f", {per_hour} req/h" if per_hour else "")
        + f" (source={rpm_source})"
    )
    if applied and tier in ("free", "community"):
        logger.info(
            "vnstock is on the free tier — paid tiers need the vnstock sponsor "
            "program (vnii package), or pin KACTUS_VNSTOCK_RPM_OVERRIDE."
        )
    return applied


def _tier_info() -> dict | None:
    """Best-effort ``vnai.get_user_tier()`` payload; ``None`` if unavailable.

    Expected shape: ``{"tier": str, "limits": {"per_minute": int, ...}}``.
    Never raises.
    """
    try:
        import vnai

        info = vnai.get_user_tier()
        return info if isinstance(info, dict) else None
    except Exception:  # pragma: no cover - defensive
        return None


def _tier_name_from(info: dict | None) -> str | None:
    if not info:
        return None
    name = info.get("tier") or info.get("name")
    return str(name) if name else None


def _safe_tier_name() -> str | None:
    """Best-effort vnstock tier name; ``None`` if unavailable. Never raises."""
    return _tier_name_from(_tier_info())


def _resolve_rpm(info: dict | None) -> tuple[int, str]:
    """The active requests/min budget and where it came from.

    Priority: admin override (``KACTUS_VNSTOCK_RPM_OVERRIDE``) → live
    ``vnai.get_user_tier()`` limits → static per-tier fallback → the
    authenticated/guest default.
    """
    from kactus_common.config import settings

    override = getattr(settings, "vnstock_rpm_override", None)
    if override:
        return int(override), "override"

    limits = (info or {}).get("limits") or {}
    per_minute = limits.get("per_minute")
    if isinstance(per_minute, (int, float)) and per_minute > 0:
        return int(per_minute), "detected"

    name = _tier_name_from(info)
    if name and name.lower() in _TIER_RPM:
        return _TIER_RPM[name.lower()], "fallback"
    if _AUTHENTICATED:
        return _AUTHED_RPM, "fallback"
    return _DEFAULT_RPM, "fallback"


def _active_rpm() -> int:
    rpm, _ = _resolve_rpm(_tier_info())
    return rpm


def vnstock_max_concurrency() -> int:
    """Max concurrent vnstock calls, derived from the active budget.

    Keeps concurrency well under the per-minute budget so the crawler never
    bursts past the rate limit.  Range: 1 (guest) … 8 (paid).
    """
    return max(1, min(8, _active_rpm() // 20))


def vnstock_min_interval() -> float:
    """Minimum seconds between two vnstock calls to stay inside the budget.

    Spends ``_RPM_SAFETY`` of the advertised budget: free 60 rpm → ~1.25s,
    bronze 180 → ~0.42s, guest 20 → ~3.75s.  Upgrading the account widens the
    budget with no code change.
    """
    return 60.0 / (_active_rpm() * _RPM_SAFETY)
