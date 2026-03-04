"""Tests for kactus-common settings: BaseKactusSettings, CommonSettings, and registry."""

import pytest

from kactus_common.config import (
    BaseKactusSettings,
    CommonSettings,
    _SettingsProxy,
    clear_settings,
    get_settings,
    register_settings,
)


class TestBaseKactusSettings:
    """Tests for the root settings class."""

    def test_default_values(self):
        s = BaseKactusSettings()
        assert s.app_env == "dev"
        assert s.debug is False
        assert s.log_level == "INFO"

    def test_is_dev(self):
        s = BaseKactusSettings(app_env="dev")
        assert s.is_dev() is True
        assert s.is_prod() is False

    def test_is_prod(self):
        s = BaseKactusSettings(app_env="prod")
        assert s.is_dev() is False
        assert s.is_prod() is True

    def test_extra_fields_ignored(self):
        """Extra fields should not raise an error (extra='ignore')."""
        s = BaseKactusSettings(app_env="dev", unknown_field="ignored")
        assert not hasattr(s, "unknown_field")


class TestCommonSettings:
    """Tests for CommonSettings (inherits BaseKactusSettings)."""

    def test_inherits_base(self):
        s = CommonSettings()
        assert isinstance(s, BaseKactusSettings)

    def test_default_values(self):
        s = CommonSettings()
        assert s.database_url == "postgresql://kactus:kactus@localhost:5432/kactus"
        assert s.db_path == "kactus.duckdb"
        assert s.encryption_key == ""

    def test_override_values(self):
        s = CommonSettings(db_path="/tmp/custom.duckdb", database_url="sqlite:///test.db")
        assert s.db_path == "/tmp/custom.duckdb"
        assert s.database_url == "sqlite:///test.db"

    def test_inherits_base_fields(self):
        s = CommonSettings(app_env="prod", debug=True)
        assert s.app_env == "prod"
        assert s.debug is True
        assert s.is_prod() is True


class TestSettingsRegistry:
    """Tests for register_settings / get_settings / clear_settings."""

    def setup_method(self):
        clear_settings()

    def teardown_method(self):
        clear_settings()

    def test_get_settings_raises_without_registration(self):
        with pytest.raises(RuntimeError, match="No settings registered"):
            get_settings()

    def test_register_and_get(self):
        s = CommonSettings(db_path="test.duckdb")
        register_settings(s)
        result = get_settings()
        assert result is s
        assert result.db_path == "test.duckdb"

    def test_clear_settings(self):
        register_settings(CommonSettings())
        clear_settings()
        with pytest.raises(RuntimeError):
            get_settings()

    def test_register_replaces_previous(self):
        s1 = CommonSettings(db_path="first.duckdb")
        s2 = CommonSettings(db_path="second.duckdb")
        register_settings(s1)
        register_settings(s2)
        assert get_settings().db_path == "second.duckdb"


class TestSettingsProxy:
    """Tests for the _SettingsProxy lazy accessor."""

    def setup_method(self):
        clear_settings()

    def teardown_method(self):
        clear_settings()

    def test_proxy_delegates_attribute_access(self):
        s = CommonSettings(db_path="proxy_test.duckdb")
        register_settings(s)
        proxy = _SettingsProxy()
        assert proxy.db_path == "proxy_test.duckdb"
        assert proxy.app_env == "dev"

    def test_proxy_raises_without_registration(self):
        proxy = _SettingsProxy()
        with pytest.raises(RuntimeError, match="No settings registered"):
            _ = proxy.db_path

    def test_proxy_dir(self):
        register_settings(CommonSettings())
        proxy = _SettingsProxy()
        attrs = dir(proxy)
        assert "db_path" in attrs
        assert "app_env" in attrs
