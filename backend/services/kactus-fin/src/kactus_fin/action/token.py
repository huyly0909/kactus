"""HMAC signing for action links — no database, no I/O, easy to reason about.

A token is ``<id>.<signature>``:

- ``id`` locates the :class:`ActionToken` row.
- ``signature`` is ``HMAC-SHA256`` over the row's *whole* meaning — id, user,
  action and params — so it proves two separate things.  Obviously it proves
  nobody forged the link.  Less obviously, because the params are signed and
  they live in the database, a row rewritten after issue no longer verifies: a
  token approved for "add FPT" cannot be turned into "add something else" by
  editing the row it points at.

Ids are snowflakes, which are guessable — monotonic and structured.  The
signature is therefore load-bearing on its own, not decoration on top of an
unguessable id.

Comparison uses :func:`hmac.compare_digest`; ``==`` on a MAC leaks its prefix
through timing, and this MAC guards financial actions.

The secret **fails closed**.  ``compare_digest`` over two empty strings is True,
so treating an unset secret as "sign with nothing" would accept every token
including ones nobody issued — a broken deployment that looks like a working
one, which is the same trap ``require_service_token`` avoids on the data plane.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from kactus_common.config import settings
from kactus_common.exceptions import ConfigurationError, PermissionDeniedError


def _secret() -> bytes:
    secret = getattr(settings, "action_token_secret", "") or ""
    if not secret:
        raise ConfigurationError(
            "KACTUS_ACTION_TOKEN_SECRET is not set — action links are disabled. "
            'Generate one with `python -c "import secrets; '
            'print(secrets.token_urlsafe(32))"`.'
        )
    return secret.encode()


def _canonical(token_id: int, user_id: int, action: str, params: dict) -> bytes:
    """The exact bytes that get signed.

    ``sort_keys`` + no whitespace: the signature has to survive a round trip
    through a JSON column, and dict ordering is not something to bet a MAC on.
    """
    body = json.dumps(params or {}, sort_keys=True, separators=(",", ":"))
    return f"{token_id}:{user_id}:{action}:{body}".encode()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def sign(*, token_id: int, user_id: int, action: str, params: dict) -> str:
    """Build the opaque token string that goes in the notification URL."""
    mac = hmac.new(
        _secret(), _canonical(token_id, user_id, action, params), hashlib.sha256
    ).digest()
    return f"{token_id}.{_b64(mac)}"


def parse_id(token: str) -> int:
    """Pull the row id out of a token without trusting anything else in it.

    A malformed token is a ``PermissionDeniedError`` (403), not a 400: the
    difference between "not a token" and "a token that did not verify" is not
    information worth handing to whoever is probing.
    """
    head, _, tail = token.partition(".")
    if not head or not tail or not head.isdigit():
        raise PermissionDeniedError("Invalid action token")
    return int(head)


def verify(
    token: str, *, token_id: int, user_id: int, action: str, params: dict
) -> None:
    """Raise ``PermissionDeniedError`` unless ``token`` signs exactly this row."""
    expected = sign(token_id=token_id, user_id=user_id, action=action, params=params)
    if not hmac.compare_digest(token, expected):
        raise PermissionDeniedError("Invalid action token")
