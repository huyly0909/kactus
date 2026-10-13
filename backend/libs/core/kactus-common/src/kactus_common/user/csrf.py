"""CSRF protection for cookie-authenticated routes.

The session cookie is ambient: the browser attaches it to any request aimed at
this host, including one a hostile page triggers. ``SameSite=Lax`` stops
cross-*site* POSTs, but not same-site ones (a sibling subdomain, another
localhost port) and not top-level form posts in every browser. So every unsafe
request on a session route must also carry a token the attacker cannot know.

**Token** = ``HMAC-SHA256(key=session_id, msg="kactus-csrf-v1")``. The session id
is a 128-bit httpOnly secret, so the token cannot be forged without reading that
cookie, and it is one-way, so a leaked token does not reveal the session. It
rotates with the session (new id at every login) and needs no secret, no column
and no migration.

**Delivery** is double-submit: a JS-readable ``kactus_xsrf_token`` cookie that
the client echoes in ``X-XSRF-TOKEN``. The server never trusts that cookie — it
recomputes the expected value from the session cookie — so a tossed cookie
(attacker sets cookie and header to the same value) still fails.

This is deliberately *not* the textbook ``header == cookie`` check. That naive
form uses the cookie as the server's memory of the token, which is only sound if
no attacker can *write* the cookie — and any sibling subdomain can, by setting it
with ``Domain=<parent>`` (Django documents this as a known bypass). Here the
session id is that memory, so the cookie is a delivery channel only: the server
reads it solely to decide whether a safe request should re-issue it. A tossed
``kactus_xsrf_token`` can therefore cause 403s (the client may echo the wrong
duplicate), never a forged request; closing that too needs the ``__Host-``
cookie prefix, which requires HTTPS.

Never return the token in a response body: the cookie is the only channel, and
a ``Set-Cookie`` header is unreadable to every other origin.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request, Response
from kactus_common.config import settings
from kactus_common.exceptions import PermissionDeniedError

from .const import (
    CSRF_COOKIE_NAME,
    CSRF_FORM_FIELD,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_ERROR_CODE = "CSRF_FAILED"

_TOKEN_CONTEXT = b"kactus-csrf-v1"
_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def csrf_token_for(session_id: str) -> str:
    """The CSRF token bound to *session_id* (deterministic, hex)."""
    return hmac.new(session_id.encode(), _TOKEN_CONTEXT, hashlib.sha256).hexdigest()


def set_csrf_cookie(response: Response, session_id: str, *, max_age: int) -> None:
    """Issue the token cookie — the session cookie's attributes, minus httpOnly."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token_for(session_id),
        max_age=max_age,
        httponly=False,  # the SPA must read it to echo it. Subdomain can't read this, because host-only
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def delete_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _csrf_failed(message: str) -> PermissionDeniedError:
    # The base class with a code override, not a subclass: the exception handler
    # looks up the exact type, and a subclass would fall through to 400.
    return PermissionDeniedError(message, code=CSRF_ERROR_CODE)


async def verify_csrf(request: Request, response: Response) -> None:
    """FastAPI dependency — runs on every session/superuser route, after auth.

    * Safe method: re-issue the cookie when it is missing or stale (a session
      created before this check existed, or a cleared cookie), then pass.
    * Unsafe method: require the token in ``X-XSRF-TOKEN``. A plain HTML form
      cannot set a header, so a urlencoded body may carry it in ``csrf_token``
      instead — used only by the action-link confirmation page.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        # Unreachable behind real auth (no cookie → 401 first); fail closed.
        raise _csrf_failed("CSRF token missing or invalid")
    expected = csrf_token_for(session_id)

    if request.method in SAFE_METHODS:
        if request.cookies.get(CSRF_COOKIE_NAME) != expected:
            # A token that outlives its session is inert: it is derived from
            # that session id, and the next login overwrites it.
            set_csrf_cookie(
                response, session_id, max_age=settings.session_remember_expiry
            )
        return

    supplied = request.headers.get(CSRF_HEADER_NAME)
    if supplied is None and request.headers.get("content-type", "").startswith(
        _FORM_CONTENT_TYPE
    ):
        field = (await request.form()).get(CSRF_FORM_FIELD)
        supplied = field if isinstance(field, str) else None

    # Against the session-derived value, never the kactus_xsrf_token cookie: an
    # extra ``cookie == header`` check would stop no attacker that this one lets
    # through (one who knows the token can toss a matching cookie too), only
    # add false 403s.
    # Bytes, not str: compare_digest raises TypeError on non-ASCII str, which
    # would turn a junk header into a 500 instead of a 403.
    if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise _csrf_failed("CSRF token missing or invalid")
