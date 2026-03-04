"""
kactus-fin application settings.

Inherits the full chain::

    BaseKactusSettings → CommonSettings → DataSettings → Settings

``Settings`` loads ``.env`` from the kactus-fin package root.
All inherited env variables (database_url, db_path, data_source, …) are
populated from that single ``.env`` file.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from kactus_common.config import register_settings
from kactus_data.config import DataSettings


class Settings(DataSettings):
    """kactus-fin settings — entry-point package that loads .env."""

    app_name: str = "Kactus Fin"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 17600

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
