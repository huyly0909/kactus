"""Tests for kactus-fin settings: Settings inheritance and get_settings."""

import pytest

from kactus_common.config import (
    BaseKactusSettings,
    CommonSettings,
    clear_settings,
    get_settings as get_global_settings,
)
from kactus_data.config import DataSettings
from kactus_fin.config import Settings, get_settings


class TestFinSettings:
    """Tests for kactus-fin Settings (inherits DataSettings)."""

    def test_inherits_data_settings(self):
        s = Settings()
        assert isinstance(s, DataSettings)
        assert isinstance(s, CommonSettings)
        assert isinstance(s, BaseKactusSettings)

    def test_default_values(self):
        s = Settings()
        assert s.app_name == "Kactus Fin"
        assert s.app_version == "0.1.0"
        assert s.host == "0.0.0.0"
        assert s.port == 17600
        assert s.session_cookie_secure is False
        assert s.session_expiry == 7 * 24 * 3600
        assert s.session_remember_expiry == 365 * 24 * 3600

    def test_inherited_common_defaults(self):
        """CommonSettings fields are available via inheritance."""
        s = Settings()
        assert s.database_url == "postgresql://kactus:kactus@localhost:5432/kactus"
        assert s.db_path == "kactus.duckdb"
        assert s.encryption_key == ""

    def test_inherited_data_defaults(self):
        """DataSettings fields are available via inheritance."""
        s = Settings()
        assert s.data_source == "KBS"

    def test_inherited_base_defaults(self):
        """BaseKactusSettings fields are available via inheritance."""
        s = Settings()
        assert s.app_env == "dev"
        assert s.debug is False
        assert s.log_level == "INFO"

    def test_env_prefix(self):
        assert Settings.model_config["env_prefix"] == "KACTUS_"

    def test_env_override(self, monkeypatch):
        """Env vars with KACTUS_ prefix override all inherited defaults."""
        monkeypatch.setenv("KACTUS_APP_NAME", "Custom Fin")
        monkeypatch.setenv("KACTUS_PORT", "9999")
        monkeypatch.setenv("KACTUS_DB_PATH", "/data/fin.duckdb")
        monkeypatch.setenv("KACTUS_DATA_SOURCE", "VCI")
        monkeypatch.setenv("KACTUS_APP_ENV", "prod")
        s = Settings()
        assert s.app_name == "Custom Fin"
        assert s.port == 9999
        assert s.db_path == "/data/fin.duckdb"
        assert s.data_source == "VCI"
        assert s.app_env == "prod"
        assert s.is_prod() is True

    def test_extra_fields_ignored(self):
        s = Settings(unknown_field="ignored")
        assert not hasattr(s, "unknown_field")

    def test_mro(self):
        """Verify the full method resolution order."""
        mro_names = [c.__name__ for c in Settings.__mro__]
        assert mro_names.index("Settings") < mro_names.index("DataSettings")
        assert mro_names.index("DataSettings") < mro_names.index("CommonSettings")
        assert mro_names.index("CommonSettings") < mro_names.index("BaseKactusSettings")


class TestFinGetSettings:
    """Tests for kactus-fin get_settings() with auto-registration."""

    def setup_method(self):
        clear_settings()
        get_settings.cache_clear()

    def teardown_method(self):
        clear_settings()
        get_settings.cache_clear()

    def test_returns_fin_settings(self):
        s = get_settings()
        assert isinstance(s, Settings)

    def test_auto_registers_in_global_registry(self):
        s = get_settings()
        global_s = get_global_settings()
        assert global_s is s

    def test_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_global_proxy_access(self):
        """After get_settings(), kactus_common.config.settings proxy works."""
        from kactus_common.config import settings

        get_settings()  # register
        assert settings.app_name == "Kactus Fin"
        assert settings.db_path == "kactus.duckdb"
