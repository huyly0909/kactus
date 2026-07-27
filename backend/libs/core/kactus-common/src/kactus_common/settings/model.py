"""Global-settings ORM model — one typed config row per (entity_type, entity_id).

Generic infrastructure (like ``SyncJob``): the discriminator ``entity_type`` +
a ``config`` JSON, coerced by the per-type schema in ``registry``. Postgres, so
config survives restarts and carries audit (who last changed it).
"""

from __future__ import annotations

from kactus_common.database.oltp.models import AuditMixin, Base, ModelMixin
from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class GlobalSettings(Base, ModelMixin, AuditMixin):
    """One settings row. ``config`` is validated against ``entity_type``'s schema."""

    __tablename__ = "global_settings"

    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        # One config row per (entity_type, entity_id). Declared for both dialects:
        # Postgres in prod, SQLite in unit tests.
        Index(
            "uq_global_settings_entity",
            "entity_type",
            "entity_id",
            unique=True,
        ),
    )
