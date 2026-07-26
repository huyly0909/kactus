"""``AuditLog`` — one append-only row per user action.

Mirrors ``NotificationLog`` / ``CrawlRun``: no ``AuditMixin`` (rows carry their
own ``user_id``/``project_id`` snapshot) and no ``LogicalDeleteMixin`` (audit
rows are immutable and never deleted from the app). ``create_time``
(``ModelMixin``) is the event timestamp.
"""

from __future__ import annotations

from kactus_common.database.oltp.models import Base, ModelMixin
from kactus_common.database.oltp.types import UnsignedBigInt
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .const import AuditOutcome


class AuditLog(Base, ModelMixin):
    """An immutable record of one user-initiated action."""

    __tablename__ = "audit_logs"

    #: Who performed the action (snapshot from the request ContextVar).
    user_id: Mapped[UnsignedBigInt | None] = mapped_column(index=True, default=None)
    #: Which project it happened in (snapshot; None for unscoped/admin actions).
    project_id: Mapped[UnsignedBigInt | None] = mapped_column(index=True, default=None)
    #: Dotted verb, e.g. ``portfolio.create`` / ``project.member.add``.
    action: Mapped[str] = mapped_column(String(64), index=True)
    #: Resource kind, e.g. ``portfolio`` (None for actions with no single target).
    resource_type: Mapped[str | None] = mapped_column(
        String(32), index=True, default=None
    )
    resource_id: Mapped[UnsignedBigInt | None] = mapped_column(index=True, default=None)
    outcome: Mapped[str] = mapped_column(String(16), default=AuditOutcome.SUCCESS)
    #: Free-form context — params, before/after, etc.
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
