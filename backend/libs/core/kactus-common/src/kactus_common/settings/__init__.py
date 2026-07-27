"""Shared global-settings infrastructure — typed, per-entity config in Postgres.

A single ``global_settings`` table holds one ``config`` JSON per
``(entity_type, entity_id)``. Each entity type registers a Pydantic schema
(``register_settings_schema``); loading a row resolves that schema by
``entity_type`` and validates/coerces the JSON into a typed object — so callers
get pre-validated settings, exactly like the notification ``CHANNEL_CONFIG_SCHEMAS``
registry.

Only the machinery lives here (infrastructure, no domain content): each domain
lib registers its own entity types from its own module — e.g. ``kactus_gold``
registers the gold availability schedule on import. An entry-point package that
serves a domain's settings must therefore import that domain lib (via
``INSTALLED_PACKAGES``) so the registration side effect runs.
"""
