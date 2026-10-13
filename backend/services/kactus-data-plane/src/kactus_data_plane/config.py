"""kactus-data-plane settings.

Inherits::

    BaseKactusSettings → CommonSettings → DataSettings → Settings

The data plane is the branch of the tree that keeps the ETL knobs — data source,
vnstock key, DuckDB path — which is the point of the split: after it,
kactus-fin's settings no longer carry any of them.

Loads the same ``KACTUS_`` prefix as kactus-fin so one ``.env`` can serve both
in a compose stack; ``database_url`` in particular MUST point at the same
Postgres, since the crawl audit rows (``CrawlRun``) and the watchlist union it
crawls both live there.
"""

from functools import lru_cache
from typing import ClassVar

from kactus_common.config import register_settings
from kactus_data.config import DataSettings
from pydantic_settings import SettingsConfigDict


class Settings(DataSettings):
    """kactus-data-plane settings — entry-point package that loads .env."""

    INSTALLED_PACKAGES: ClassVar[list[str]] = DataSettings.INSTALLED_PACKAGES + [
        "kactus_data_plane"
    ]

    app_name: str = "Kactus Data Plane"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 17602

    # The crawl scheduler. On by default — running it is this service's job.
    # Turn it off to get a read-only data plane (useful when replaying a crawl
    # by hand, or to keep a staging copy from competing for the vnstock quota).
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
