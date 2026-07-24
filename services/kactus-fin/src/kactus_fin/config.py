"""
kactus-fin application settings.

Merges two branches of the settings tree::

    BaseKactusSettings ─┬─ CommonSettings ─────────┬─ Settings
                        └─ NotificationSettings ───┘

kactus-fin is the only entry point that sends notifications, so it is the only
one that mixes ``NotificationSettings`` in — the gateway's settings do not carry
``zalo_pa_*`` at all.

It no longer inherits ``DataSettings``: after the data-plane split this process
neither crawls nor opens DuckDB, so ``data_source``, ``vnstock_api_key`` and
``db_path`` are not its business. They live on kactus-data-server's settings.
What replaced them is ``data_plane_url`` + ``internal_service_token`` on
``CommonSettings`` — the address of the service that does own them.

``Settings`` loads ``.env`` from the kactus-fin package root; all inherited env
variables are populated from that single file.
"""

from functools import lru_cache
from typing import ClassVar

from kactus_common.config import CommonSettings, register_settings
from kactus_notification.config import NotificationSettings
from pydantic_settings import SettingsConfigDict


class Settings(CommonSettings, NotificationSettings):
    """kactus-fin settings — entry-point package that loads .env."""

    # Extend, never overwrite: a replaced list drops the upstream MODELS and
    # Alembic autogenerate emits DROP TABLE for every table it can no longer see.
    #
    # ``kactus_data`` drops off the list with the dependency. It is safe only
    # because it declares no ORM models — every Postgres table the crawler
    # touches (CrawlRun, SupportedAsset, PortfolioItem) is defined in
    # kactus-common and still loaded. If the data plane ever adds a table of its
    # own, it must be declared here, because kactus-fin still owns the single
    # Alembic head for the shared database.
    INSTALLED_PACKAGES: ClassVar[list[str]] = CommonSettings.INSTALLED_PACKAGES + [
        "kactus_notification",
        "kactus_fin",
    ]

    app_name: str = "Kactus Fin"
    app_version: str = "0.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 17600

    # Action links (kactus_fin/action/) — the signed one-time URLs that ride in
    # a notification. The secret fails closed: unset means action links cannot
    # be issued *or* verified, which is the right default for a link that
    # authorises something on a user's behalf. `localhost` default per
    # .claude/rules/docker-conventions.md; set the real public URL per env or
    # the link in a chat message points at the reader's own machine.
    action_token_secret: str = ""
    action_token_ttl_secs: int = 900  # 15 min — long enough to notice a phone buzz
    public_base_url: str = "http://localhost:17600"

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
