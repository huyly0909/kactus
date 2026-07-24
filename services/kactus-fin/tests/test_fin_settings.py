"""Tests for kactus-fin settings: Settings inheritance and get_settings."""

from kactus_common.config import BaseKactusSettings, CommonSettings, clear_settings
from kactus_common.config import get_settings as get_global_settings
from kactus_fin.config import Settings, get_settings
from kactus_notification.config import NotificationSettings


class TestFinSettings:
    """Tests for kactus-fin Settings (CommonSettings + NotificationSettings)."""

    def test_merges_both_branches(self):
        s = Settings()
        assert isinstance(s, CommonSettings)
        assert isinstance(s, NotificationSettings)
        assert isinstance(s, BaseKactusSettings)

    def test_does_not_inherit_data_settings(self):
        """The ETL knobs left with the data plane.

        Not a style preference: kactus-fin has no kactus-data dependency any
        more, so importing DataSettings here would not even resolve. Asserting
        on the field is the cheap version of that check.
        """
        assert not hasattr(Settings(), "data_source")

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

    def test_data_plane_defaults(self):
        """How this process finds the service that does own the ETL."""
        s = Settings()
        assert s.data_plane_url == "http://localhost:17602"
        assert s.internal_service_token == ""

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
        monkeypatch.setenv("KACTUS_DATA_PLANE_URL", "http://data:17602")
        monkeypatch.setenv("KACTUS_APP_ENV", "prod")
        s = Settings()
        assert s.app_name == "Custom Fin"
        assert s.port == 9999
        assert s.db_path == "/data/fin.duckdb"
        assert s.data_plane_url == "http://data:17602"
        assert s.app_env == "prod"
        assert s.is_prod() is True

    def test_extra_fields_ignored(self):
        s = Settings(unknown_field="ignored")
        assert not hasattr(s, "unknown_field")

    def test_mro(self):
        """Verify the full method resolution order.

        CommonSettings must precede NotificationSettings: both descend from
        BaseKactusSettings, and this is the order that decides which branch wins
        if the two ever declare the same field name.
        """
        mro_names = [c.__name__ for c in Settings.__mro__]
        assert mro_names.index("Settings") < mro_names.index("CommonSettings")
        assert mro_names.index("CommonSettings") < mro_names.index(
            "NotificationSettings"
        )
        assert mro_names.index("NotificationSettings") < mro_names.index(
            "BaseKactusSettings"
        )


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
