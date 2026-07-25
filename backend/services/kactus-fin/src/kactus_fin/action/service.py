"""Issue, verify and consume action tokens.

The ordering of checks in :meth:`ActionTokenService.resolve` is deliberate and
should stay this way:

1. **signature** — before anything else, so a forged or edited token gets 403
   without revealing whether that id exists at all;
2. **owner** — 403, same reason;
3. **consumed** — 409, "you already did this";
4. **expired** — 410, "this link timed out".

Reversing 3 and 4 would tell a user whose link expired *after* they used it that
it had expired, which is the less useful of the two true statements.
"""

from __future__ import annotations

import datetime

from kactus_common.config import settings
from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import (
    ConflictError,
    GoneError,
    InvalidArgumentError,
    PermissionDeniedError,
)
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from .const import ActionType
from .model import ActionToken
from .registry import ACTION_HANDLERS
from .token import parse_id, sign, verify


class ActionTokenService:
    """Lifecycle of a one-time action link."""

    @staticmethod
    async def issue(
        session: AsyncSession,
        *,
        user_id: int,
        action: ActionType,
        params: dict | None = None,
        ttl_secs: int | None = None,
    ) -> tuple[ActionToken, str]:
        """Create a token row and return it with its signed string.

        The row is written first so the id exists to sign; the signature covers
        that id, which is why this cannot be a single INSERT.
        """
        if action not in ACTION_HANDLERS:
            # Unreachable via the enum, but an unhandled action would issue a
            # link that 500s when clicked — better to fail at issue time.
            raise InvalidArgumentError(f"No handler registered for action {action}")

        ttl = ttl_secs or settings.action_token_ttl_secs
        params = params or {}

        token_row = ActionToken.init(
            user_id=user_id,
            action=str(action),
            params=params,
            expires_at=utcnow() + datetime.timedelta(seconds=ttl),
        )
        session.add(token_row)
        await session.commit()
        await session.refresh(token_row)

        token = sign(
            token_id=token_row.id,
            user_id=user_id,
            action=str(action),
            params=params,
        )
        return token_row, token

    @staticmethod
    def url_for(token: str) -> str:
        """The link that goes into ``NotificationEvent.url``."""
        base = settings.public_base_url.rstrip("/")
        return f"{base}/api/actions/{token}"

    @staticmethod
    async def resolve(
        session: AsyncSession, token: str, *, user_id: int
    ) -> ActionToken:
        """Load and fully validate a token **without** consuming it.

        Used by both GET and POST: the confirmation page must reject an expired
        or already-used link just as firmly as the execution does, it simply
        must not change anything on the way.
        """
        row = await ActionToken.get(session, parse_id(token))
        if row is None:
            raise PermissionDeniedError("Invalid action token")

        verify(
            token,
            token_id=row.id,
            user_id=row.user_id,
            action=row.action,
            params=row.params or {},
        )

        if row.user_id != user_id:
            raise PermissionDeniedError("This action link belongs to another account")
        if row.consumed_at is not None:
            raise ConflictError("This action link has already been used")
        if row.expires_at <= utcnow():
            raise GoneError("This action link has expired — request a new one")
        return row

    @staticmethod
    async def consume(session: AsyncSession, row: ActionToken) -> None:
        """Mark the token used, atomically.

        A conditional UPDATE rather than read-modify-write: two POSTs arriving
        together would both pass the ``consumed_at is None`` check in
        :meth:`resolve` and both execute.  The database decides the winner, and
        the loser gets the same 409 as an ordinary double-click.
        """
        result = await session.execute(
            update(ActionToken)
            .where(ActionToken.id == row.id, ActionToken.consumed_at.is_(None))
            .values(consumed_at=utcnow())
        )
        await session.commit()
        if result.rowcount == 0:
            raise ConflictError("This action link has already been used")

    @staticmethod
    async def execute(session: AsyncSession, row: ActionToken) -> str:
        """Consume the token, then run the action.

        Consume first: a handler that fails halfway (the data plane is down, the
        asset is already in the portfolio) must not leave a live link behind
        that re-runs whatever it did manage to do.  The user asks for a new link
        instead, which is the safe direction to fail in for anything touching
        money.
        """
        await ActionTokenService.consume(session, row)
        handler = ACTION_HANDLERS[ActionType(row.action)]
        return await handler(session, row.user_id, row.params or {})
