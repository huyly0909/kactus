"""
kactus-fin-gateway application settings.

Inherits::

    BaseKactusSettings → CommonSettings → Settings

Loads ``.env`` from the gateway package with ``KACTUS_GW_`` prefix.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from kactus_common.config import CommonSettings, register_settings


class Settings(CommonSettings):
    """kactus-fin-gateway settings — entry-point package that loads .env."""

    app_name: str = "Kactus Fin Gateway"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 17601

    model_config = SettingsConfigDict(
        env_prefix="KACTUS_GW_",
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
