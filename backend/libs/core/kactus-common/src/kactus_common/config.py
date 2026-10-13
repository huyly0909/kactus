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

from typing import ClassVar

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

    # Packages whose MODELS list should be imported by load_models()
    INSTALLED_PACKAGES: ClassVar[list[str]] = ["kactus_common"]

    # OLTP database (PostgreSQL / MySQL)
    database_url: str = "postgresql://kactus:kactus@localhost:5432/kactus"
    sqlalchemy_echo: bool = False
    sqlalchemy_pool_size: int = 5

    # OLAP database (DuckDB)
    db_path: str = "kactus.duckdb"

    # Redis — coordination between processes (locks, cache, SSE fan-out, TTL
    # session stores).  NOT a job queue and NOT a source of truth: audit rows
    # stay in Postgres, commands between services go over HTTP.
    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "kactus"  # namespace, so one Redis can host several envs

    # Where cross-process state lives.  ONE switch on purpose, covering both the
    # SSE broker and the Zalo QR session store: a deployment that enables one but
    # not the other is broken in a way nothing reports — SSE would fan out
    # correctly while QR logins silently fail whenever the 5 steps land on
    # different workers.
    #
    #   memory — per-process. Correct ONLY at --workers 1.
    #   redis  — shared. Required before raising the worker count.
    #
    # Explicit rather than "redis if reachable": a silent fallback to memory
    # would look healthy while quietly delivering to a quarter of the clients.
    coordination_backend: str = "memory"  # "memory" | "redis"

    # Data plane — where the DuckDB owner lives, and the shared secret that
    # fences its /internal routes off.  Both halves sit here because kactus-fin
    # (the caller) and kactus-data-plane (the callee) no longer share any
    # settings branch below this one: fin dropped its kactus-data dependency
    # when the planes split.
    #
    # localhost default per .claude/rules/docker-conventions.md; compose
    # overrides it with the service name.
    data_plane_url: str = "http://localhost:17602"
    # Empty is a hard failure on the data plane, not a permissive default — see
    # kactus_data_plane.security. There is no anonymous access to /internal.
    internal_service_token: str = ""
    data_plane_timeout: float = 30.0

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
