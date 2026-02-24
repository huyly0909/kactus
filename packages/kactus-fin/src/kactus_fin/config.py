from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Kactus Fin"
    app_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 17600

    # Database
    db_path: str = "kactus.duckdb"
    database_url: str = "postgresql://kactus:kactus@localhost:5432/kactus"

    # Auth / Crypto
    encryption_key: str = ""  # Fernet key — generate with CryptoService.generate_key()
    session_cookie_secure: bool = False  # True in prod (HTTPS-only cookies)
    session_expiry: int = 7 * 24 * 3600  # 7 days
    session_remember_expiry: int = 365 * 24 * 3600  # 1 year

    model_config = {
        "env_prefix": "KACTUS_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
