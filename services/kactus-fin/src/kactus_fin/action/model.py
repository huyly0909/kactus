"""``ActionToken`` — one row per issued action link.

The row, not the signature, is what makes a token one-time: ``consumed_at`` is
set by a conditional UPDATE, so two simultaneous POSTs cannot both win. The HMAC
in the URL only proves the token was issued by us and has not been edited since;
by itself it says nothing about whether it has already been used, which is
exactly why a stateless JWT would be the wrong shape here.

No ``LogicalDeleteMixin``: consumed and expired tokens stay as an audit trail of
what was approved and when. They are cheap and small; pruning is a housekeeping
job, not a delete flag.
"""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import AuditMixin, Base, ModelMixin
from kactus_common.database.oltp.types import UnsignedBigInt
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class ActionToken(Base, ModelMixin, AuditMixin):
    """A single-use authorisation to run one action on one user's behalf."""

    __tablename__ = "action_tokens"

    #: Whose action this is. The request's session user must match — the token
    #: alone is not a credential, it is a *pre-authorisation* for someone we
    #: have already identified.
    user_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    #: Arguments for the handler (portfolio_id, code, …). Signed along with the
    #: rest, so a row edited after issue fails verification.
    #:
    #: Named ``params`` rather than ``payload`` because ``ModelMixin.init``
    #: already takes a positional ``payload`` for bulk construction —
    #: ``ActionToken.init(payload={...})`` would be read as "these are all the
    #: columns" and raise on the first key.
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime.datetime] = mapped_column(index=True)
    consumed_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
