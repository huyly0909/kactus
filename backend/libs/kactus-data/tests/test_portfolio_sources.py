"""Coverage for market normalization, providers (stock+gold), scheduler,
catalog/ohlcv jobs, and vnstock auth — all without network access."""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest
import pytest_asyncio
from kactus_common.config import clear_settings, register_settings
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.service import SupportedAssetService
from kactus_data.config import DataSettings
from kactus_data.exceptions import RateLimitedError
from kactus_data.jobs.crawl import crawl_ohlcv_blocking, sync_catalog
from kactus_data.jobs.scheduler import build_scheduler
from kactus_data.portfolio.provider import (
    GoldAssetProvider,
    StockAssetProvider,
    build_providers,
)
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.stock.market import StockMarketSource
from kactus_data.storage.duckdb import DuckDBStorage


class FullFakeMarket(StockMarketSource):
    """Overrides every raw vnstock seam with synthetic data."""

    def _raw_price_board(self, codes):
        return pd.DataFrame([{"symbol": c, "match_price": 1.0} for c in codes])

    def _raw_news(self, code):
        return pd.DataFrame(
            [
                {
                    "id": f"{code}-n",
                    "title": "Tin",
                    "public_date": "2026-01-01",
                    "url": "u",
                }
            ]
        )

    def _raw_events(self, code):
        return pd.DataFrame(
            [{"id": f"{code}-e", "event_title": "ĐHCĐ", "event_date": "2026-01-02"}]
        )

    def _raw_ratio(self, code):
        return pd.DataFrame([{"period": "2026Q1", "pe": 10.0}])

    def _raw_foreign_trade(self, code):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2026-01-01",
                    "buy_value": 100,
                    "sell_value": 40,
                    "net_value": 60,
                }
            ]
        )

    def _raw_all_symbols(self):
        return pd.DataFrame(
            [
                {"symbol": "FPT", "organ_name": "FPT Corp", "exchange": "HOSE"},
                {"symbol": "VCB", "organ_name": "Vietcombank", "exchange": "HOSE"},
            ]
        )

    def _raw_group(self, group):
        return ["FPT"] if group == "VN30" else ["FPT", "VCB"]


class TransposedRatioMarket(FullFakeMarket):
    """vnstock 4.x returns ratios *transposed*: metrics as rows, quarters as
    columns.  Mirrors the live FPT shape so the pivot/PK logic is exercised."""

    def _raw_ratio(self, code):
        return pd.DataFrame(
            [
                {"item": "Năm", "item_id": "year", "2025-Q1": 2025, "2025-Q2": 2025},
                {"item": "P/E", "item_id": "pe", "2025-Q1": 18.1, "2025-Q2": 17.4},
                {"item": "P/B", "item_id": "pb", "2025-Q1": 4.2, "2025-Q2": 4.0},
            ]
        )


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    """Zero the vnstock pacing sleep so the suite stays fast."""
    monkeypatch.setattr(
        "kactus_data.sources.stock.market.vnstock_min_interval", lambda: 0.0
    )
    monkeypatch.setattr("kactus_data.jobs.crawl.vnstock_min_interval", lambda: 0.0)


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url="sqlite+aiosqlite://")
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    await manager.close()


@pytest.fixture
def storage(tmp_path):
    return DuckDBStorage(str(tmp_path / "src.duckdb"))


# --------------------------------------------------------------- market source
def test_market_normalizes_all_datasets():
    m = FullFakeMarket(source="VCI")
    assert m.price_board(["FPT"]).iloc[0]["symbol"] == "FPT"
    assert m.news(["FPT"]).iloc[0]["news_id"] == "FPT-n"
    assert m.events(["FPT"]).iloc[0]["title"] == "ĐHCĐ"
    assert m.foreign_trade(["FPT"]).iloc[0]["net_value"] == 60.0
    assert m.ratios(["FPT"]).iloc[0]["period"] == "2026Q1"


def test_market_catalog_tags_indices():
    entries = {e["code"]: e for e in FullFakeMarket().catalog()}
    assert entries["FPT"]["tags"] == ["VN30", "VN100"]
    assert entries["VCB"]["tags"] == ["VN100"]
    assert entries["FPT"]["name"] == "FPT Corp"


def test_market_flatten_multiindex_columns():
    from kactus_data.sources.stock.market import _flatten_columns

    df = pd.DataFrame(
        [[1, 2]], columns=pd.MultiIndex.from_tuples([("a", "b"), ("c", "")])
    )
    flat = _flatten_columns(df)
    assert list(flat.columns) == ["a_b", "c"]


# ------------------------------------------------------------------- providers
@pytest.mark.parametrize("kind", [CrawlKind.NEWS, CrawlKind.RATIOS, CrawlKind.EVENTS])
def test_stock_provider_crawl_and_read(storage, kind):
    # decision-support kinds read from decision_market, so fake both seams.
    provider = StockAssetProvider(storage, FullFakeMarket(), FullFakeMarket())
    assert kind in provider.supported_kinds()
    assert provider.crawl(kind, ["FPT"]) == 1
    rows = provider.read(kind, ["FPT"])
    assert len(rows) == 1
    assert rows[0]["symbol"] == "FPT"


def test_ratios_transposed_frame_pivots_per_quarter(storage):
    """vnstock 4.x transposed ratio frame → one row per (symbol, quarter).

    Regression for the live PK collision: the pre-pivot code stamped every row
    ``period="quarter"`` → ``(symbol, period)`` UPSERT crash.
    """
    m = TransposedRatioMarket(source="VCI")
    df = m.ratios(["FPT"])
    assert sorted(df["period"]) == ["2025-Q1", "2025-Q2"]
    assert df["period"].nunique() == len(df)  # PK (symbol, period) is unique
    import json as _json

    metrics = _json.loads(df.iloc[0]["raw_json"])
    assert metrics["pe"] in (18.1, 17.4) and "pb" in metrics

    # Full crawl path must store both quarters without a constraint error.
    provider = StockAssetProvider(storage, FullFakeMarket(), TransposedRatioMarket())
    assert provider.crawl(CrawlKind.RATIOS, ["FPT"]) == 2
    assert len(provider.read(CrawlKind.RATIOS, ["FPT"])) == 2


def test_decision_kinds_use_decision_market(storage):
    """news/events/ratios route to decision_market (VCI), not the quotes market."""

    class EmptyMarket(FullFakeMarket):
        def _raw_news(self, code):
            return pd.DataFrame()

        def _raw_events(self, code):
            return pd.DataFrame()

    # quotes market is "empty" for news; decision_market has data → rows come
    # from decision_market, proving the routing.
    provider = StockAssetProvider(storage, EmptyMarket(), FullFakeMarket())
    assert provider.crawl(CrawlKind.NEWS, ["FPT"]) == 1
    # and the reverse: a working quotes market does not rescue an empty decision one
    provider2 = StockAssetProvider(storage, FullFakeMarket(), EmptyMarket())
    assert provider2.crawl(CrawlKind.NEWS, ["FPT"]) == 0


def test_stock_provider_foreign_trade_unsupported(storage):
    """foreign_trade is not wired — VCI (vnstock 4.x) doesn't implement it."""
    provider = StockAssetProvider(storage, FullFakeMarket())
    assert CrawlKind.FOREIGN_TRADE not in provider.supported_kinds()
    assert provider.crawl(CrawlKind.FOREIGN_TRADE, ["FPT"]) == 0
    assert provider.read(CrawlKind.FOREIGN_TRADE, ["FPT"]) == []


def test_stock_provider_fetch_catalog(storage):
    provider = StockAssetProvider(storage, FullFakeMarket())
    assert {e["code"] for e in provider.fetch_catalog()} == {"FPT", "VCB"}


class FakeMihong:
    """mihong stub — quotes VND/chỉ, so the provider must scale ×10."""

    name = "mihong"

    def __init__(self, xsrf_token=None):
        self.xsrf_token = xsrf_token

    def sync(self, s, e, code):
        return SyncDataResponse(
            success=True,
            data_source="mihong",
            code=code,
            start_date="",
            end_date="",
            data=[{"buyingPrice": 13657142, "sellingPrice": 13914285}],
            timestamp="",
        )


class DeadSjc:
    """SJC board unreachable (Cloudflare) → provider falls back to mihong."""

    name = "sjc"

    def fetch_board(self):
        return []

    def quote(self, code, board=None):
        return None


class LiveSjc(DeadSjc):
    """SJC board reachable — already VND/lượng, must be stored unscaled."""

    def fetch_board(self):
        return [{"TypeName": "Vàng SJC 1L, 10L, 1KG", "BranchName": "Hồ Chí Minh"}]

    def quote(self, code, board=None):
        if str(code).upper() != "SJC":
            return None
        return {"buy_price": 134500000.0, "sell_price": 139500000.0, "raw": {}}


class DualSjc(LiveSjc):
    """SJC quoting both its products — the bar (SJC) and the ring (999).

    Real sjc.com.vn does this; mihong quotes 999 too, which is exactly the
    pair the ``(code, source)`` board keys must keep apart.
    """

    def quote(self, code, board=None):
        if str(code).upper() == "SJC":
            return {"buy_price": 134500000.0, "sell_price": 139500000.0, "raw": {}}
        if str(code).upper() == "999":
            return {"buy_price": 138500000.0, "sell_price": 142500000.0, "raw": {}}
        return None


class FakeYahoo:
    """World-gold stub — quotes USD/oz, so the row must NOT be scaled."""

    name = "yahoo"

    def latest(self):
        return {
            "date": "2026-07-24",
            "close": 4037.6999,
            "open": 4020.0,
            "high": 4041.0,
            "low": 4015.0,
        }


class DeadYahoo(FakeYahoo):
    def latest(self):
        return None


def _patch_gold(monkeypatch, sjc_cls, yahoo_cls=FakeYahoo):
    monkeypatch.setattr("kactus_data.portfolio.provider.MihongGoldSource", FakeMihong)
    monkeypatch.setattr("kactus_data.portfolio.provider.SjcGoldSource", sjc_cls)
    monkeypatch.setattr("kactus_data.portfolio.provider.YahooGoldSource", yahoo_cls)


def test_gold_provider_prefers_sjc_official(monkeypatch, storage):
    """sjc.com.vn is the issuer reference — it wins over mihong."""
    _patch_gold(monkeypatch, LiveSjc)
    provider = GoldAssetProvider(storage)
    assert {e["code"] for e in provider.fetch_catalog()} >= {"SJC", "999"}
    assert provider.crawl(CrawlKind.QUOTES, ["SJC"]) == 1
    rows = provider.read(CrawlKind.QUOTES, ["SJC"])
    assert rows[0]["code"] == "SJC"
    assert rows[0]["buy_price"] == 134500000.0
    assert rows[0]["source"] == "sjc"


def test_gold_provider_falls_back_to_mihong_scaled(monkeypatch, storage):
    """SJC down → mihong takes over, VND/chỉ scaled ×10 to VND/lượng."""
    _patch_gold(monkeypatch, DeadSjc)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["SJC"]) == 1
    rows = provider.read(CrawlKind.QUOTES, ["SJC"])
    assert rows[0]["buy_price"] == 136571420.0  # 13,657,142 × 10
    assert rows[0]["sell_price"] == 139142850.0
    assert rows[0]["source"] == "mihong"


def test_gold_provider_no_token_required(monkeypatch, storage):
    """Regression: gold used to be skipped without an XSRF token."""
    _patch_gold(monkeypatch, DeadSjc)
    assert (
        GoldAssetProvider(storage, xsrf_token="").crawl(CrawlKind.QUOTES, ["SJC"]) == 1
    )


def test_gold_board_keeps_both_sources_for_999(monkeypatch, storage):
    """SJC-999 and Mihong-999 are different products — the board keeps both.

    Regression: with PK ``code`` alone the upsert deleted by code, so a
    mihong sync was silently overwritten by SJC and users saw ``source=sjc``
    on a row they had just synced from mihong.
    """
    _patch_gold(monkeypatch, DualSjc)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["999"]) == 2

    board = storage.query("SELECT * FROM gold_price_board")
    assert set(zip(board["code"], board["source"])) == {
        ("999", "sjc"),
        ("999", "mihong"),
    }
    by_source = {r["source"]: r for r in board.to_dict(orient="records")}
    assert float(by_source["sjc"]["buy_price"]) == 138500000.0
    assert float(by_source["mihong"]["buy_price"]) == 136571420.0  # ×10 scaled


def test_gold_read_collapses_to_one_quote_per_code(monkeypatch, storage):
    """A portfolio holding of "999" is one position — read() returns one row.

    Ties on ``crawled_at`` (the normal case: one crawl stamps every row with
    the same instant) go to SJC, the issuer reference.
    """
    _patch_gold(monkeypatch, DualSjc)
    provider = GoldAssetProvider(storage)
    provider.crawl(CrawlKind.QUOTES, ["999"])

    rows = provider.read(CrawlKind.QUOTES, ["999"])
    assert len(rows) == 1
    assert rows[0]["source"] == "sjc"


def test_gold_read_prefers_the_fresher_source(monkeypatch, storage):
    """Freshest wins — that is what keeps mihong acting as the SJC fallback.

    mihong no longer overwrites SJC's row, so "SJC is stale because Cloudflare
    blocked us" has to be expressed by ``crawled_at`` instead.
    """
    _patch_gold(monkeypatch, DualSjc)
    provider = GoldAssetProvider(storage)
    provider.crawl(CrawlKind.QUOTES, ["999"])
    # Age SJC's row by an hour, leaving mihong's as the only recent quote.
    storage.query(
        "UPDATE gold_price_board SET crawled_at = crawled_at - INTERVAL 1 HOUR "
        "WHERE code = '999' AND source = 'sjc'"
    )

    rows = provider.read(CrawlKind.QUOTES, ["999"])
    assert len(rows) == 1
    assert rows[0]["source"] == "mihong"


def test_gold_provider_skips_unsupported_and_kinds(monkeypatch, storage):
    """DOJI/PNJ have no feed on either source; NEWS is not a gold kind."""
    _patch_gold(monkeypatch, DeadSjc)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["DOJI", "PNJ"]) == 0
    assert provider.crawl(CrawlKind.NEWS, ["SJC"]) == 0
    assert provider.crawl(CrawlKind.QUOTES, []) == 0


def test_gold_rows_record_their_price_unit(monkeypatch, storage):
    """The board mixes VND/lượng and USD/oz — each row must say which."""
    _patch_gold(monkeypatch, LiveSjc)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["SJC", "XAU"]) == 2

    by_code = {r["code"]: r for r in provider.read(CrawlKind.QUOTES, ["SJC", "XAU"])}
    assert by_code["SJC"]["unit"] == "VND/luong"
    assert by_code["XAU"]["unit"] == "USD/oz"


def test_gold_provider_crawls_world_gold_unscaled(monkeypatch, storage):
    """XAU comes from Yahoo in USD/oz — the ×10 chỉ→lượng scaling must not apply."""
    _patch_gold(monkeypatch, DeadSjc)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["XAU"]) == 1

    row = provider.read(CrawlKind.QUOTES, ["XAU"])[0]
    assert row["source"] == "yahoo"
    # World gold has no bid/ask on the chart API, so both sides carry the close.
    assert float(row["buy_price"]) == pytest.approx(4037.6999)
    assert float(row["sell_price"]) == pytest.approx(4037.6999)


def test_gold_provider_survives_yahoo_outage(monkeypatch, storage):
    """A dead Yahoo drops XAU but must not take the domestic codes down."""
    _patch_gold(monkeypatch, LiveSjc, yahoo_cls=DeadYahoo)
    provider = GoldAssetProvider(storage)
    assert provider.crawl(CrawlKind.QUOTES, ["SJC", "XAU"]) == 1
    assert [r["code"] for r in provider.read(CrawlKind.QUOTES, ["SJC", "XAU"])] == [
        "SJC"
    ]


def test_gold_catalog_lists_enabled_codes(monkeypatch, storage):
    """The catalog is exactly the three wired codes — DOJI/PNJ were dropped."""
    _patch_gold(monkeypatch, LiveSjc)
    catalog = {e["code"]: e for e in GoldAssetProvider(storage).fetch_catalog()}

    assert set(catalog) == {"SJC", "999", "XAU"}
    for code in ("SJC", "999", "XAU"):
        assert catalog[code]["meta_json"]["enabled"] is True
        assert "disabled" not in catalog[code]["tags"]
        assert catalog[code]["is_crawlable"] is True

    assert catalog["XAU"]["meta_json"]["unit"] == "USD/oz"
    assert catalog["SJC"]["meta_json"]["unit"] == "VND/luong"


def test_build_providers_registry(storage):
    providers = build_providers(storage, data_source="VCI", mihong_token="t")
    assert set(providers) == {AssetType.STOCK, AssetType.GOLD}
    assert AssetType.COIN not in providers  # deferred


# ------------------------------------------------------------------- scheduler
@pytest.mark.asyncio
async def test_build_scheduler_registers_jobs(db):
    scheduler = build_scheduler(db=db)
    ids = {j.id for j in scheduler.get_jobs()}
    assert {
        "crawl_quotes",
        "crawl_news",
        "crawl_ratios",
        "crawl_events",
        "crawl_ohlcv",
        "sync_catalog",
    } <= ids
    # foreign_trade is intentionally not scheduled (unsupported by VCI in 4.x)
    assert "crawl_foreign_trade" not in ids


# ------------------------------------------------------------------- jobs
@pytest.mark.asyncio
async def test_sync_catalog_upserts(db, storage):
    providers = {AssetType.STOCK: StockAssetProvider(storage, FullFakeMarket())}
    out = await sync_catalog(db=db, providers=providers, asset_types=[AssetType.STOCK])
    assert out[str(AssetType.STOCK)] == 2
    async with db.get_session() as session:
        found = await SupportedAssetService.search(session, asset_type=AssetType.STOCK)
    assert {a.code for a in found} == {"FPT", "VCB"}


def test_crawl_ohlcv_blocking(monkeypatch, storage):
    def fake_sync(self, start, end, code):
        return SyncDataResponse(
            success=True,
            data_source="vnstock_ohlcv",
            code=code,
            start_date="",
            end_date="",
            data=[
                {
                    "symbol": code,
                    "time": "2026-01-01 00:00:00",
                    "interval": "1D",
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 1000.0,
                    "source": "VCI",
                }
            ],
            timestamp="",
        )

    monkeypatch.setattr(
        "kactus_data.sources.stock.vnstock.VnstockOHLCVSource.sync", fake_sync
    )
    assert crawl_ohlcv_blocking(storage, ["FPT"], days=3) == 1
    assert crawl_ohlcv_blocking(storage, []) == 0


def test_crawl_ohlcv_blocking_rate_limit_keeps_partial(monkeypatch, storage):
    """SystemExit on the 2nd code → RateLimitedError carrying the stored count."""
    calls = {"n": 0}

    def fake_sync(self, start, end, code):
        calls["n"] += 1
        if calls["n"] > 1:
            raise SystemExit("Rate limit exceeded")
        return SyncDataResponse(
            success=True,
            data_source="vnstock_ohlcv",
            code=code,
            start_date="",
            end_date="",
            data=[
                {
                    "symbol": code,
                    "time": "2026-01-01 00:00:00",
                    "interval": "1D",
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 1000.0,
                    "source": "VCI",
                }
            ],
            timestamp="",
        )

    monkeypatch.setattr(
        "kactus_data.sources.stock.vnstock.VnstockOHLCVSource.sync", fake_sync
    )
    with pytest.raises(RateLimitedError) as exc_info:
        crawl_ohlcv_blocking(storage, ["FPT", "VCB"], days=3)
    ex = exc_info.value
    assert (ex.done, ex.total, ex.rows_stored) == (1, 2, 1)


# ------------------------------------------------------------------- auth
def test_init_vnstock_auth_with_key(monkeypatch):
    fake = types.ModuleType("vnai")
    captured = {}
    fake.setup_api_key = lambda k: captured.setdefault("key", k)
    fake.get_user_tier = lambda: {
        "tier": "free",
        "limits": {"per_minute": 60, "per_hour": 3600},
    }
    monkeypatch.setitem(sys.modules, "vnai", fake)
    register_settings(DataSettings(vnstock_api_key="secret-key"))
    import kactus_data.sources.stock.auth as auth

    try:
        assert auth.init_vnstock_auth() is True
        assert captured["key"] == "secret-key"
        assert auth._safe_tier_name() == "free"
        assert auth._active_rpm() == 60  # detected via get_user_tier
        assert auth.vnstock_max_concurrency() == 3  # 60 // 20
    finally:
        auth._AUTHENTICATED = False
        clear_settings()


def test_rpm_override_beats_detection(monkeypatch):
    """KACTUS_VNSTOCK_RPM_OVERRIDE pins the budget over anything detected."""
    import kactus_data.sources.stock.auth as auth

    monkeypatch.setattr(
        auth, "_tier_info", lambda: {"tier": "free", "limits": {"per_minute": 60}}
    )
    register_settings(DataSettings(vnstock_rpm_override=300))
    try:
        rpm, source = auth._resolve_rpm(auth._tier_info())
        assert (rpm, source) == (300, "override")
        assert auth.vnstock_max_concurrency() == 8  # 300//20=15, capped at 8
        # Pacing widens with the budget: 60/(300*0.8) = 0.25s between calls.
        assert auth.vnstock_min_interval() == pytest.approx(0.25)
    finally:
        clear_settings()


def test_rpm_falls_back_to_static_tier_table(monkeypatch):
    """Detection names a paid tier but gives no limits → static table."""
    import kactus_data.sources.stock.auth as auth

    register_settings(DataSettings())
    try:
        rpm, source = auth._resolve_rpm({"tier": "Bronze"})
        assert (rpm, source) == (180, "fallback")
    finally:
        clear_settings()


def test_rpm_authenticated_unnamed_tier(monkeypatch):
    """Key applied but vnai unavailable → assume the 60rpm authed budget."""
    import kactus_data.sources.stock.auth as auth

    register_settings(DataSettings())
    monkeypatch.setattr(auth, "_AUTHENTICATED", True)
    monkeypatch.setattr(auth, "_tier_info", lambda: None)
    try:
        assert auth._active_rpm() == 60
        assert auth.vnstock_max_concurrency() == 3
    finally:
        clear_settings()


def test_rpm_guest_when_unauthenticated(monkeypatch):
    """No key, no tier info → guest budget (20 rpm, concurrency 1, ~3.75s gap)."""
    import kactus_data.sources.stock.auth as auth

    register_settings(DataSettings())
    monkeypatch.setattr(auth, "_AUTHENTICATED", False)
    monkeypatch.setattr(auth, "_tier_info", lambda: None)
    try:
        assert auth._active_rpm() == 20
        assert auth.vnstock_max_concurrency() == 1
        assert auth.vnstock_min_interval() == pytest.approx(3.75)
    finally:
        clear_settings()


def test_init_vnstock_auth_no_key(monkeypatch):
    import kactus_data.sources.stock.auth as auth

    register_settings(DataSettings(vnstock_api_key=""))
    monkeypatch.setattr(auth, "_tier_info", lambda: None)
    try:
        assert auth.init_vnstock_auth() is False
    finally:
        clear_settings()


# ------------------------------------------------------------------- CLI
def test_cli_crawl_and_sync(monkeypatch):
    import kactus_data.cli.portfolio as pcli
    from typer.testing import CliRunner

    class FakeProvider:
        def supported_kinds(self):
            return {CrawlKind.QUOTES}

        def crawl(self, kind, codes):
            return len(codes)

    async def fake_sync_catalog(**kwargs):
        return {"STOCK": 5}

    providers = {AssetType.STOCK: FakeProvider()}
    monkeypatch.setattr(pcli, "_bootstrap", lambda: (None, providers))
    monkeypatch.setattr(pcli, "sync_catalog", fake_sync_catalog)

    runner = CliRunner()
    r = runner.invoke(pcli.cli, ["crawl", "--kind", "quotes", "--codes", "FPT,VCB"])
    assert r.exit_code == 0
    assert "2" in r.stdout

    r = runner.invoke(pcli.cli, ["sync-catalog", "--asset-type", "stock"])
    assert r.exit_code == 0

    # Empty codes is rejected.
    r = runner.invoke(pcli.cli, ["crawl", "--codes", " "])
    assert r.exit_code == 1

    # Unsupported kind for the provider is rejected.
    r = runner.invoke(pcli.cli, ["crawl", "--kind", "news", "--codes", "FPT"])
    assert r.exit_code == 1
