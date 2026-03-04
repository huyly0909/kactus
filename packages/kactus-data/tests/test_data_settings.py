"""Tests for kactus-data settings: DataSettings and get_settings."""

import os

import pytest

from kactus_common.config import (
    BaseKactusSettings,
    CommonSettings,
    clear_settings,
    get_settings as get_global_settings,
)
from kactus_data.config import DataSettings, get_settings


class TestDataSettings:
    """Tests for DataSettings (inherits CommonSettings)."""

    def test_inherits_common(self):
        s = DataSettings()
        assert isinstance(s, CommonSettings)
        assert isinstance(s, BaseKactusSettings)

    def test_default_values(self):
        s = DataSettings()
        assert s.data_source == "KBS"
        assert s.db_path == "kactus.duckdb"
        assert s.database_url == "postgresql://kactus:kactus@localhost:5432/kactus"
        assert s.app_env == "dev"

    def test_override_values(self):
        s = DataSettings(data_source="VCI", db_path="/tmp/test.duckdb")
        assert s.data_source == "VCI"
        assert s.db_path == "/tmp/test.duckdb"

    def test_env_prefix(self):
        """DataSettings uses KACTUS_ prefix for env vars."""
        assert DataSettings.model_config["env_prefix"] == "KACTUS_"

    def test_env_override(self, monkeypatch):
        """Env vars with KACTUS_ prefix override defaults."""
        monkeypatch.setenv("KACTUS_DATA_SOURCE", "VCI")
        monkeypatch.setenv("KACTUS_DB_PATH", "/data/custom.duckdb")
        s = DataSettings()
        assert s.data_source == "VCI"
        assert s.db_path == "/data/custom.duckdb"

    def test_extra_fields_ignored(self):
        s = DataSettings(unknown="ignored")
        assert not hasattr(s, "unknown")

    def test_mro(self):
        """Verify the method resolution order."""
        mro_names = [c.__name__ for c in DataSettings.__mro__]
        assert mro_names.index("DataSettings") < mro_names.index("CommonSettings")
        assert mro_names.index("CommonSettings") < mro_names.index("BaseKactusSettings")


class TestDataGetSettings:
    """Tests for DataSettings get_settings() with auto-registration."""

    def setup_method(self):
        clear_settings()
        get_settings.cache_clear()

    def teardown_method(self):
        clear_settings()
        get_settings.cache_clear()

    def test_returns_data_settings(self):
        s = get_settings()
        assert isinstance(s, DataSettings)

    def test_auto_registers_in_global_registry(self):
        s = get_settings()
        global_s = get_global_settings()
        assert global_s is s

    def test_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
