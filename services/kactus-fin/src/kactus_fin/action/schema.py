"""Schemas for issuing action links."""

from __future__ import annotations

import datetime

from kactus_common.schemas import BaseSchema, FancyInt

from .const import ActionType


class ActionIssueRequest(BaseSchema):
    """Ask for a one-time link that will run ``action`` with ``params``."""

    action: ActionType
    params: dict = {}
    #: Override the default TTL. Kept short on purpose — an action link is a
    #: standing authorisation, and the window it stays valid is the window an
    #: intercepted message is worth something.
    ttl_secs: int | None = None


class ActionLinkSchema(BaseSchema):
    """The issued link. ``url`` is what goes into ``NotificationEvent.url``."""

    id: FancyInt
    action: ActionType
    token: str
    url: str
    expires_at: datetime.datetime
