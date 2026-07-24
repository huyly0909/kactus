"""Alembic env.py — configured for kactus-fin with autogenerate support."""

from logging.config import fileConfig

from alembic import context

# Import Base and load_models
from kactus_common.app_registry import load_models
from kactus_common.database.oltp.models import Base

# Import app settings to get the database URL
from kactus_fin.config import get_settings
from sqlalchemy import engine_from_config, pool

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

#: Async driver → the sync equivalent Alembic can actually use.
#:
#: The app runs on asyncpg, but ``run_migrations_online`` below builds a plain
#: ``engine_from_config``. Handing that an async driver fails at connect() with
#: ``MissingGreenlet: greenlet_spawn has not been called`` — a message that says
#: nothing about the real cause. ``psycopg2-binary`` is a kactus-fin dependency
#: for exactly this reason.
_SYNC_DRIVERS = {"+asyncpg": "+psycopg2", "+aiosqlite": ""}


def _sync_url(url: str) -> str:
    for async_driver, sync_driver in _SYNC_DRIVERS.items():
        if async_driver in url:
            return url.replace(async_driver, sync_driver)
    return url


# Override sqlalchemy.url from app settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", _sync_url(settings.database_url))

# Load all ORM models declared by installed packages
load_models(settings)

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Tables managed by this migration — ignore everything else in the DB
# MANAGED_TABLES = {"users", "user_sessions"}


# def include_object(object, name, type_, reflected, compare_to):
#     """Only include tables we manage; skip unknown tables already in DB."""
#     if type_ == "table":
#         return name in MANAGED_TABLES
#     return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
