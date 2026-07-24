"""Service-to-service auth for ``/internal``.

A shared secret in ``X-Service-Token``, nothing more. That is enough because
this service is not routed from the internet: compose puts it on the internal
network and stag/prod publish no port for it. The token is the second lock, for
the case where something else lands on that network.

There is deliberately no per-user authorization here. The control plane decides
who may see which portfolio, in one place; if the data plane re-derived that it
would be a second copy of the rules to keep in sync, and the two would
eventually disagree. What reaches this service has already been authorized.
"""

from __future__ import annotations

import hmac

from fastapi import Header
from kactus_common.config import settings
from kactus_common.exceptions import ConfigurationError, PermissionDeniedError


async def require_service_token(
    x_service_token: str = Header(default="", alias="X-Service-Token"),
) -> None:
    """Reject anything without the shared secret.

    An unset ``KACTUS_INTERNAL_SERVICE_TOKEN`` fails every request rather than
    waving them through: an empty configured secret compared against an empty
    header would otherwise make the whole surface anonymous, which is exactly
    the mistake this guard exists to prevent. Loud and broken beats quiet and
    open.
    """
    expected = getattr(settings, "internal_service_token", "")
    if not expected:
        raise ConfigurationError(
            "KACTUS_INTERNAL_SERVICE_TOKEN is not set — /internal is unusable "
            "until the data plane and the control plane share a secret."
        )
    # compare_digest: a plain == leaks the position of the first wrong byte
    # through timing, which is enough to recover a secret one byte at a time.
    if not hmac.compare_digest(x_service_token, expected):
        raise PermissionDeniedError("Invalid or missing X-Service-Token")
