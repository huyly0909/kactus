"""Tests for kactus-fin-gateway settings: Settings inheritance and get_settings."""

import pytest

from kactus_common.config import (
    BaseKactusSettings,
    CommonSettings,
    clear_settings,
    get_settings as get_global_settings,
)
from kactus_fin_gateway.config import Settings, get_settings


class TestGatewaySettings:
    """Tests for kactus-fin-gateway Settings (inherits CommonSettings)."""

    def test_inherits_common(self):
        s = Settings()
        assert isinstance(s, CommonSettings)
        assert isinstance(s, BaseKactusSettings)

    def test_default_values(self):
        s = Settings()
        assert s.app_name == "Kactus Fin Gateway"
        assert s.app_version == "0.1.0"
        assert s.host == "0.0.0.0"
        assert s.port == 17601

    def test_inherited_common_defaults(self):
        """CommonSettings fields are available via inheritance."""
        s = Settings()
        assert s.database_url == "postgresql://kactus:kactus@localhost:5432/kactus"
        assert s.db_path == "kactus.duckdb"
        assert s.encryption_key == ""

    def test_inherited_base_defaults(self):
        """BaseKactusSettings fields are available via inheritance."""
        s = Settings()
        assert s.app_env == "dev"
        assert s.debug is False
        assert s.log_level == "INFO"

    def test_does_not_have_data_settings(self):
        """Gateway does NOT inherit DataSettings — no data_source field."""
        s = Settings()
        assert not hasattr(s, "data_source")

    def test_env_prefix(self):
        assert Settings.model_config["env_prefix"] == "KACTUS_GW_"

    def test_env_override(self, monkeypatch):
        """Env vars with KACTUS_GW_ prefix override defaults."""
        monkeypatch.setenv("KACTUS_GW_APP_NAME", "Custom Gateway")
        monkeypatch.setenv("KACTUS_GW_PORT", "8888")
        monkeypatch.setenv("KACTUS_GW_DB_PATH", "/data/gw.duckdb")
        monkeypatch.setenv("KACTUS_GW_APP_ENV", "prod")
        s = Settings()
        assert s.app_name == "Custom Gateway"
        assert s.port == 8888
        assert s.db_path == "/data/gw.duckdb"
        assert s.app_env == "prod"
        assert s.is_prod() is True

    def test_extra_fields_ignored(self):
        s = Settings(unknown_field="ignored")
        assert not hasattr(s, "unknown_field")

    def test_mro(self):
        """Verify the method resolution order."""
        mro_names = [c.__name__ for c in Settings.__mro__]
        assert mro_names.index("Settings") < mro_names.index("CommonSettings")
        assert mro_names.index("CommonSettings") < mro_names.index("BaseKactusSettings")


class TestGatewayGetSettings:
    """Tests for kactus-fin-gateway get_settings() with auto-registration."""

    def setup_method(self):
        clear_settings()
        get_settings.cache_clear()

    def teardown_method(self):
        clear_settings()
        get_settings.cache_clear()

    def test_returns_gateway_settings(self):
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
        assert settings.app_name == "Kactus Fin Gateway"
        assert settings.db_path == "kactus.duckdb"
