"""Tests for kactus-fin-gateway: imports, config, health endpoint."""

import pytest
from fastapi.testclient import TestClient


class TestImports:
    def test_import_package(self):
        import kactus_fin_gateway
        assert kactus_fin_gateway is not None

    def test_import_app(self):
        from kactus_fin_gateway.app import app, create_app
        assert app is not None
        assert create_app is not None

    def test_import_config(self):
        from kactus_fin_gateway.config import Settings, get_settings
        assert Settings is not None

    def test_cross_package_import(self):
        from kactus_common.exceptions import KactusException
        from kactus_common.database.oltp import DatabaseSessionManager
        assert KactusException is not None
        assert DatabaseSessionManager is not None


class TestConfig:
    def test_default_settings(self):
        from kactus_fin_gateway.config import Settings
        settings = Settings()
        assert settings.app_name == "Kactus Fin Gateway"
        assert settings.port == 8001
        assert settings.debug is False

    def test_env_prefix(self):
        from kactus_fin_gateway.config import Settings
        assert Settings.model_config["env_prefix"] == "KACTUS_GW_"


class TestAppFactory:
    def test_create_app(self):
        from kactus_fin_gateway.app import create_app
        from fastapi import FastAPI
        app = create_app()
        assert isinstance(app, FastAPI)
        assert app.title == "Kactus Fin Gateway"

    def test_routes_registered(self):
        from kactus_fin_gateway.app import create_app
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/health" in routes


class TestHealthEndpoint:
    @pytest.fixture
    def client(self):
        from kactus_fin_gateway.app import create_app
        return TestClient(create_app())

    def test_health_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_body(self, client):
        assert client.get("/health").json() == {"status": "ok"}


class TestExceptionHandler:
    """Test that KactusException handler is wired correctly."""

    def test_not_found_returns_404(self):
        from kactus_fin_gateway.app import create_app
        from kactus_common.exceptions import NotFoundError
        from fastapi import FastAPI

        app = create_app()

        @app.get("/test-404")
        async def raise_not_found():
            raise NotFoundError("item not found", tip="check ID")

        client = TestClient(app)
        resp = client.get("/test-404")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "NOT_FOUND"
        assert body["message"] == "item not found"
        assert body["tip"] == "check ID"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
