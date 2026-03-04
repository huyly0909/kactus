"""
Kactus base settings and settings registry.

Design:
    - ``BaseKactusSettings`` — root settings class, does NOT load .env files.
    - ``CommonSettings`` — settings owned by kactus-common (DB, crypto, etc.).
    - Settings registry — allows shared modules to access the running app's
      settings via ``from kactus_common.config import settings`` without
      importing from downstream packages (no circular imports).

Each downstream package (kactus-data, kactus-fin, kactus-fin-gateway)
creates its own Settings class that inherits from ``CommonSettings``
(or from another package's settings) and loads its own ``.env`` file.

Architecture::

    BaseKactusSettings          ← app_env, debug, log_level
      └── CommonSettings        ← database_url, db_path, encryption_key
          ├── DataSettings      ← data_source (kactus-data)
          │   └── fin Settings  ← host, port, … (loads .env)
          └── gw Settings       ← host, port, … (loads .env)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Base settings
# ---------------------------------------------------------------------------


class BaseKactusSettings(BaseSettings):
    """Root settings class — inherited by every package.

    Does NOT load ``.env`` files.  Subclasses in entry-point packages
    set ``model_config`` with ``env_file`` to load a specific ``.env``.
    """

    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "dev"
    debug: bool = False
    log_level: str = "INFO"

    def is_dev(self) -> bool:
        return self.app_env == "dev"

    def is_prod(self) -> bool:
        return self.app_env == "prod"


class CommonSettings(BaseKactusSettings):
    """Settings owned by kactus-common.

    Contains infrastructure variables shared across all packages:
    database connections, crypto keys, session/auth config, etc.
    """

    # OLTP database (PostgreSQL / MySQL)
    database_url: str = "postgresql://kactus:kactus@localhost:5432/kactus"
    sqlalchemy_echo: bool = False
    sqlalchemy_pool_size: int = 5

    # OLAP database (DuckDB)
    db_path: str = "kactus.duckdb"

    # Crypto
    encryption_key: str = ""  # Fernet key — generate with CryptoService.generate_key()

    # Session / Auth
    session_cookie_secure: bool = False  # True in prod (HTTPS-only cookies)
    session_expiry: int = 7 * 24 * 3600  # 7 days
    session_remember_expiry: int = 365 * 24 * 3600  # 1 year


# ---------------------------------------------------------------------------
# Settings registry
# ---------------------------------------------------------------------------

_current_settings: BaseKactusSettings | None = None


def register_settings(settings: BaseKactusSettings) -> None:
    """Register the running app's settings instance.

    Called once at app startup (e.g. in ``create_app()`` or CLI init).
    """
    global _current_settings
    _current_settings = settings


def get_settings() -> BaseKactusSettings:
    """Return the registered settings.

    Raises:
        RuntimeError: If no settings have been registered yet.
    """
    if _current_settings is None:
        raise RuntimeError(
            "No settings registered. Call register_settings() in your "
            "app's initialization code (e.g. create_app() or CLI init)."
        )
    return _current_settings


def clear_settings() -> None:
    """Clear the registered settings (useful for testing)."""
    global _current_settings
    _current_settings = None


# ---------------------------------------------------------------------------
# Proxy — ``from kactus_common.config import settings``
# ---------------------------------------------------------------------------


class _SettingsProxy:
    """Proxy that delegates attribute access to the registered settings.

    Provides type hints for IDE autocomplete while allowing dynamic
    registration at runtime.
    """

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __dir__(self):
        return dir(get_settings())


# Export as CommonSettings for type hints
settings: CommonSettings = _SettingsProxy()  # type: ignore
