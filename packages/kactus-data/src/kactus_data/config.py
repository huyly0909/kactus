"""
kactus-data settings.

``DataSettings`` inherits ``CommonSettings`` from kactus-common and adds
data-specific configuration (e.g. default data source).

Standalone usage (kactus-data CLI)::

    from kactus_data.config import get_settings

    settings = get_settings()
    print(settings.db_path)       # from .env or default
    print(settings.data_source)   # from .env or default

When kactus-fin inherits ``DataSettings``, the fin ``.env`` file
supplies values for all inherited fields — ``get_settings()`` in
kactus-data is NOT called in that scenario.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from kactus_common.config import CommonSettings, register_settings


class DataSettings(CommonSettings):
    """Settings owned by kactus-data.

    Inherits all ``CommonSettings`` fields (database_url, db_path, etc.)
    and adds data-pipeline-specific configuration.

    When used standalone (via ``get_settings()``), loads ``.env`` with
    the ``KACTUS_`` prefix.  When inherited by a downstream package
    (e.g. kactus-fin), that package's ``model_config`` takes precedence.
    """

    data_source: str = "KBS"

    model_config = SettingsConfigDict(
        env_prefix="KACTUS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> DataSettings:
    """Return cached DataSettings and register in the global registry.

    Called automatically when kactus-data runs standalone (CLI).
    NOT called when kactus-fin inherits DataSettings — fin has its own
    ``get_settings()`` that registers fin's Settings instead.
    """
    s = DataSettings()
    register_settings(s)
    return s
