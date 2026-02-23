#!/usr/bin/env python3
"""
Tests for kactus-fin package: app factory, config, health endpoint, and cross-package imports.
"""

import pytest
from fastapi.testclient import TestClient


class TestImports:
    """Verify all kactus-fin modules import correctly."""

    def test_import_package(self):
        """Test top-level package import."""
        import kactus_fin
        assert kactus_fin is not None

    def test_import_app(self):
        """Test app module import."""
        from kactus_fin.app import app, create_app
        assert app is not None
        assert create_app is not None

    def test_import_config(self):
        """Test config module import."""
        from kactus_fin.config import Settings, get_settings
        assert Settings is not None
        assert get_settings is not None

    def test_import_health_router(self):
        """Test health router import."""
        from kactus_fin.api.health import router
        assert router is not None

    def test_cross_package_import_kactus_common(self):
        """Test that kactus-common is accessible from kactus-fin."""
        from kactus_common.database.duckdb.client import DatabaseClient
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
        assert DatabaseClient is not None
        assert DataType is not None


class TestConfig:
    """Tests for the Settings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        from kactus_fin.config import Settings
        settings = Settings()
        assert settings.app_name == "Kactus Fin"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.db_path == "kactus.duckdb"

    def test_settings_env_prefix(self):
        """Test that settings use the KACTUS_ env prefix."""
        from kactus_fin.config import Settings
        assert Settings.model_config["env_prefix"] == "KACTUS_"

    def test_get_settings_returns_instance(self):
        """Test that get_settings returns a Settings instance."""
        from kactus_fin.config import get_settings, Settings
        # Clear the lru_cache for a clean test
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)


class TestAppFactory:
    """Tests for the FastAPI app factory."""

    def test_create_app_returns_fastapi(self):
        """Test that create_app returns a FastAPI instance."""
        from kactus_fin.app import create_app
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title(self):
        """Test that app has correct title."""
        from kactus_fin.app import create_app
        app = create_app()
        assert app.title == "Kactus Fin"

    def test_app_version(self):
        """Test that app has correct version."""
        from kactus_fin.app import create_app
        app = create_app()
        assert app.version == "0.1.0"

    def test_app_has_routes(self):
        """Test that app has registered routes."""
        from kactus_fin.app import create_app
        app = create_app()
        routes = [route.path for route in app.routes]
        assert "/health" in routes


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from kactus_fin.app import create_app
        app = create_app()
        return TestClient(app)

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok(self, client):
        """Test health endpoint returns correct body."""
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_health_content_type(self, client):
        """Test health endpoint returns JSON."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
