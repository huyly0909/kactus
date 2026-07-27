"""The settings schema registry — one Pydantic schema per entity_type.

Mirrors the notification ``CHANNEL_CONFIG_SCHEMAS`` data-shape registry: each
entity type registers a :class:`BaseSchema` (and optionally a default factory);
``parse_settings_config`` validates a raw ``config`` dict against it. Consumers
register from their own module in ``kactus_common`` (never an upward import).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pydantic
from kactus_common.exceptions import ConfigurationError, ValidationError
from kactus_common.schemas import BaseSchema


def _no_default(entity_id: str) -> dict | None:
    """Default factory that yields no defaults (a missing row → NotFoundError)."""
    return None


@dataclass(frozen=True)
class SettingsSpec:
    """How one entity type's config is validated + its lazy defaults."""

    schema: type[BaseSchema]
    #: Given an ``entity_id``, return the default config dict (or ``None`` for
    #: "no default", i.e. a missing row is a genuine 404).
    default_factory: Callable[[str], dict | None] = _no_default


#: entity_type (str) -> its SettingsSpec. Populated by ``register_settings_schema``.
SETTINGS_SPECS: dict[str, SettingsSpec] = {}


def register_settings_schema(
    entity_type: str,
    schema: type[BaseSchema],
    *,
    default_factory: Callable[[str], dict | None] | None = None,
) -> None:
    """Register the config schema (and optional defaults) for an entity type."""
    SETTINGS_SPECS[str(entity_type)] = SettingsSpec(
        schema=schema,
        default_factory=default_factory or _no_default,
    )


def get_spec(entity_type: str) -> SettingsSpec:
    """Resolve a registered spec, or fail closed on an unknown entity type.

    An unknown type is a misconfiguration (a consumer forgot to register), not
    bad user input — so it raises ``ConfigurationError``, not ``ValidationError``.
    """
    spec = SETTINGS_SPECS.get(str(entity_type))
    if spec is None:
        raise ConfigurationError(
            f"No settings schema registered for entity_type '{entity_type}'"
        )
    return spec


def parse_settings_config(entity_type: str, config: dict | None) -> BaseSchema:
    """Validate a raw config dict against its per-type schema.

    Re-raises a pydantic failure as a 400 ``ValidationError`` (as the
    notification service does), so a bad stored/submitted config is a clean
    client error rather than a 500.
    """
    spec = get_spec(entity_type)
    try:
        return spec.schema.model_validate(config or {})
    except pydantic.ValidationError as exc:
        # Compact, JSON-safe error strings (a raw errors() dict can carry a
        # non-serialisable ``ctx`` exception object).
        errors = [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
            for e in exc.errors(include_url=False)
        ]
        raise ValidationError(
            f"Invalid settings config for '{entity_type}'",
            data={"errors": errors},
        ) from exc
