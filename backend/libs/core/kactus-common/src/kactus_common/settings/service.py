"""Read/write lifecycle for global settings — stateless, like ``SyncJobService``.

``load`` returns the typed, validated config for an entity: the stored row if
present, else the registered lazy default (or ``NotFoundError`` if the entity
type has no default). ``upsert`` validates then writes the single row per
``(entity_type, entity_id)`` — wired for a future admin editor, not an endpoint yet.
"""

from __future__ import annotations

from kactus_common.exceptions import NotFoundError
from kactus_common.schemas import BaseSchema
from sqlalchemy.ext.asyncio import AsyncSession

from .model import GlobalSettings
from .registry import get_spec, parse_settings_config


class GlobalSettingsService:
    """Resolve, read, and write typed per-entity settings."""

    @staticmethod
    async def load(
        session: AsyncSession, *, entity_type: str, entity_id: str
    ) -> BaseSchema:
        """The validated config for one entity (stored row → lazy default → 404)."""
        spec = get_spec(entity_type)
        row = await GlobalSettings.first(
            session, entity_type=str(entity_type), entity_id=entity_id
        )
        if row is not None:
            return parse_settings_config(entity_type, row.config)
        default = spec.default_factory(entity_id)
        if default is None:
            raise NotFoundError(f"No settings for '{entity_type}' entity '{entity_id}'")
        return parse_settings_config(entity_type, default)

    @staticmethod
    async def get_row(
        session: AsyncSession, entity_type: str, entity_id: str
    ) -> GlobalSettings | None:
        """The raw row (for the future editor), or ``None`` if unset."""
        return await GlobalSettings.first(
            session, entity_type=str(entity_type), entity_id=entity_id
        )

    @staticmethod
    async def upsert(
        session: AsyncSession, *, entity_type: str, entity_id: str, config: dict
    ) -> GlobalSettings:
        """Validate ``config`` then insert-or-update the single row (audit auto)."""
        validated = parse_settings_config(entity_type, config)
        payload = validated.model_dump(mode="json")
        row = await GlobalSettings.first(
            session, entity_type=str(entity_type), entity_id=entity_id
        )
        if row is None:
            row = GlobalSettings.init(
                entity_type=str(entity_type), entity_id=entity_id, config=payload
            )
            session.add(row)
        else:
            row.config = payload
        await session.commit()
        await session.refresh(row)
        return row
