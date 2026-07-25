"""The runtime builder and the symbol provider that feeds the crawl jobs."""

from __future__ import annotations

import pytest
from kactus_common.database.oltp import session as session_mod
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.service import PortfolioService, SupportedAssetService
from kactus_data_server.symbol_provider import WatchlistSymbolProvider


@pytest.mark.asyncio
async def test_symbol_provider_unions_watchlists_with_the_baseline(db):
    """The crawl universe is every watched symbol *plus* the index baseline.

    The baseline is there so the platform has VN30 data on day one, before any
    user has built a watchlist — otherwise a new deployment crawls nothing and
    every chart is empty.
    """
    async with db.get_session() as session:
        # FPT tagged VN30 (baseline), VCB plain — both crawlable.
        await SupportedAssetService.upsert_many(
            session,
            asset_type=AssetType.STOCK,
            entries=[{"code": "FPT", "tags": ["VN30"]}, {"code": "VCB", "tags": []}],
        )
        p = await PortfolioService.create(session, name="P", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p.id, asset_type=AssetType.STOCK, code="VCB"
        )

    codes = await WatchlistSymbolProvider(db).get_codes_by_type()
    # VCB from the watchlist union; FPT from the VN30 baseline.
    assert set(codes[str(AssetType.STOCK)]) == {"FPT", "VCB"}


@pytest.mark.asyncio
async def test_symbol_provider_reads_postgres_not_the_control_plane(db):
    """No watchlists, no baseline → nothing to crawl, and no HTTP call made.

    The provider deliberately reads the shared database rather than asking
    kactus-fin: a crawl must not be blocked by the control plane being down.
    If that ever changed, this test would need a fake HTTP server to pass.
    """
    assert await WatchlistSymbolProvider(db).get_codes_by_type() == {}


@pytest.mark.asyncio
async def test_build_runtime_without_a_scheduler(db, tmp_path, monkeypatch):
    """Covers the lifespan builder with the scheduler off and no network."""
    from kactus_common.config import clear_settings, register_settings
    from kactus_data_server import app as app_mod
    from kactus_data_server.app import build_runtime, shutdown_runtime
    from kactus_data_server.config import Settings

    # vnstock auth reaches for a key file / the network; the runtime under test
    # is the wiring around it, not the SDK. Patched on the *importing* module —
    # app.py bound the name at import time, so patching its source has no effect.
    monkeypatch.setattr(app_mod, "init_vnstock_auth", lambda *a, **kw: None)

    settings = Settings(
        enable_portfolio_scheduler=False, db_path=str(tmp_path / "rt.duckdb")
    )
    register_settings(settings)
    session_mod._db = db
    runtime = None
    try:
        runtime = build_runtime(settings)
        assert runtime.scheduler is None
        assert AssetType.STOCK in runtime.providers
        assert runtime.storage is not None
    finally:
        shutdown_runtime(runtime)
        session_mod._db = None
        clear_settings()


def test_warns_when_launched_with_multiple_workers(monkeypatch):
    """Two workers means two DuckDB write handles and two schedulers.

    A warning, not a refusal: a data plane that will not boot crawls nothing
    at all, which is strictly worse than one that crawls twice.
    """
    from kactus_data_server import app as app_mod

    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    assert app_mod._detected_worker_count() == 4

    monkeypatch.delenv("WEB_CONCURRENCY")
    monkeypatch.setattr(app_mod.sys, "argv", ["uvicorn", "--workers", "2"])
    assert app_mod._detected_worker_count() == 2

    monkeypatch.setattr(app_mod.sys, "argv", ["uvicorn"])
    assert app_mod._detected_worker_count() is None
