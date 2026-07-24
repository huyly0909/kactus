"""
kactus-fin application settings.

Merges two branches of the settings tree::

    BaseKactusSettings ─┬─ CommonSettings ── DataSettings ─┬─ Settings
                        └─ NotificationSettings ───────────┘

kactus-fin is the only entry point that sends notifications, so it is the only
one that mixes ``NotificationSettings`` in — the gateway's settings do not carry
``zalo_pa_*`` at all.

``Settings`` loads ``.env`` from the kactus-fin package root.
All inherited env variables (database_url, db_path, data_source, …) are
populated from that single ``.env`` file.
"""

from functools import lru_cache
from typing import ClassVar

from kactus_common.config import register_settings
from kactus_data.config import DataSettings
from kactus_notification.config import NotificationSettings
from pydantic_settings import SettingsConfigDict


class Settings(DataSettings, NotificationSettings):
    """kactus-fin settings — entry-point package that loads .env."""

    # Extend, never overwrite: a replaced list drops the upstream MODELS and
    # Alembic autogenerate emits DROP TABLE for every table it can no longer see.
    INSTALLED_PACKAGES: ClassVar[list[str]] = DataSettings.INSTALLED_PACKAGES + [
        "kactus_notification",
        "kactus_fin",
    ]

    app_name: str = "Kactus Fin"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 17600

    # Portfolio crawler — disable in tests / one-off CLI to avoid spinning the
    # in-process APScheduler.  Single-worker only (in-process scheduler + SSE):
    # run `uvicorn --workers 1`; scale-out needs Redis pub/sub + a Celery worker.
    enable_portfolio_scheduler: bool = True

    model_config = SettingsConfigDict(
        env_prefix="KACTUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings and register in the global registry."""
    s = Settings()
    register_settings(s)
    return s
