"""Tests for the portfolio crawl layer — queue-backed.

Uses a fake :class:`StockMarketSource` (overriding only the raw vnstock seams),
a tmp-file DuckDB, and in-memory SQLite for the sync queue — no network.  Every
crawl executes as a ``SyncJob`` now: these tests cover the handlers, the
enqueue dedup, and the dispatcher lifecycle (PENDING → RUNNING → terminal).
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
import pytest_asyncio
from kactus_common.config import clear_settings, register_settings
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.events import register_handler
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_common.portfolio.crawl_queue import (
    crawl_job_type,
    enqueue_catalog_sync,
    enqueue_crawl_jobs,
)
from kactus_common.portfolio.events import MarketEventName
from kactus_common.sync.const import SyncJobStatus
from kactus_common.sync.model import SyncJob
from kactus_common.sync.service import SyncJobService
from kactus_data.config import DataSettings
from kactus_data.exceptions import RateLimitedError

# Importing the handlers module registers every crawl job type.
from kactus_data.jobs import crawl_handlers  # noqa: F401
from kactus_data.jobs.scheduler import build_scheduler
from kactus_data.jobs.sync_queue import SYNC_HANDLERS, SyncJobDeps, _run_job, _view
from kactus_data.portfolio.provider import StockAssetProvider
from kactus_data.sources.stock.market import StockMarketSource
from kactus_data.storage.duckdb import DuckDBStorage


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    """Zero the vnstock pacing sleep so the suite stays fast."""
    monkeypatch.setattr(
        "kactus_data.sources.stock.market.vnstock_min_interval", lambda: 0.0
    )


@pytest.fixture(autouse=True)
def _settings():
    """Handlers read the settings proxy (data_source, SSE backend, rpm)."""
    register_settings(DataSettings())
    yield
    clear_settings()


class FakeMarket(StockMarketSource):
    """vnstock-free market source: only the raw seams are overridden."""

    def _raw_price_board(self, codes):
        return pd.DataFrame(
            [
                {
                    "symbol": c,
                    "match_price": 10.0,
                    "ref_price": 9.5,
                    "ceiling": 11.0,
                    "floor": 9.0,
                    "accumulated_volume": 1000,
                }
                for c in codes
            ]
        )

    def _raw_news(self, code):
        # Vietnamese text + apostrophe + newline → exercises register-insert safety.
        return pd.DataFrame(
            [
                {
                    "id": f"{code}-1",
                    "title": "Lợi nhuận 'tăng' mạnh\nquý 4 — báo cáo",
                    "public_date": "2026-06-17",
                    "url": "https://example.com/news/1",
                }
            ]
        )


class RateLimitedMarket(FakeMarket):
    """vnai's guard fires (``sys.exit``) on the second symbol of a news crawl."""

    def _raw_news(self, code):
        if code != "FPT":
            raise SystemExit("Rate limit exceeded. Vui lòng thử lại sau.")
        return super()._raw_news(code)


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url="sqlite+aiosqlite://")
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    await manager.close()


@pytest.fixture
def storage(tmp_path):
    return DuckDBStorage(str(tmp_path / "test.duckdb"))


def _deps(db, storage, provider) -> SyncJobDeps:
    return SyncJobDeps(db=db, storage=storage, providers={AssetType.STOCK: provider})


async def _get_job(db, job_id: int) -> SyncJob:
    async with db.get_session() as session:
        job = await SyncJob.get(session, job_id)
        assert job is not None
        return job


# ------------------------------------------------------------------- provider
def test_provider_crawl_quotes_roundtrip(storage):
    provider = StockAssetProvider(storage, FakeMarket(source="VCI"))
    n = provider.crawl(CrawlKind.QUOTES, ["FPT", "VCB"])
    assert n == 2
    rows = provider.read(CrawlKind.QUOTES, ["FPT"])
    assert len(rows) == 1
    assert rows[0]["symbol"] == "FPT"
    assert rows[0]["match_price"] == 10.0
    assert rows[0]["source"] == "VCI"


def test_provider_crawl_news_is_text_safe(storage):
    """Vietnamese news with quotes/newlines round-trips intact (register insert)."""
    # news routes to decision_market → back it with the same fake.
    provider = StockAssetProvider(storage, FakeMarket(), FakeMarket())
    n = provider.crawl(CrawlKind.NEWS, ["FPT"])
    assert n == 1
    rows = provider.read(CrawlKind.NEWS, ["FPT"])
    assert "tăng" in rows[0]["title"]
    assert "\n" in rows[0]["title"]
    # raw_json is valid JSON and preserves the original payload.
    raw = json.loads(rows[0]["raw_json"])
    assert raw["id"] == "FPT-1"


def test_provider_crawl_empty_codes(storage):
    provider = StockAssetProvider(storage, FakeMarket())
    assert provider.crawl(CrawlKind.QUOTES, []) == 0


def test_provider_rate_limit_stores_partial_then_raises(storage):
    """A mid-crawl rate limit stores what was fetched, then surfaces the hit."""
    provider = StockAssetProvider(storage, FakeMarket(), RateLimitedMarket())
    with pytest.raises(RateLimitedError) as exc_info:
        provider.crawl(CrawlKind.NEWS, ["FPT", "VCB", "ACB"])
    ex = exc_info.value
    assert (ex.done, ex.total) == (1, 3)
    assert ex.rows_stored == 1  # FPT's row landed before the wall
    assert len(provider.read(CrawlKind.NEWS, ["FPT"])) == 1


# ------------------------------------------------------------------- enqueue
@pytest.mark.asyncio
async def test_enqueue_crawl_jobs_captures_trigger_and_dedups(db):
    async with db.get_session() as session:
        created, existing = await enqueue_crawl_jobs(
            session, kind=CrawlKind.QUOTES, trigger=CrawlTrigger.CRON
        )
    assert {j.job_type for j in created} == {"stock_quotes", "gold_quotes"}
    assert existing == []
    assert all(j.status == str(SyncJobStatus.PENDING) for j in created)
    assert all(j.params["trigger"] == str(CrawlTrigger.CRON) for j in created)

    # Second fire while the first is still live → dedup, no new rows.
    async with db.get_session() as session:
        created2, existing2 = await enqueue_crawl_jobs(
            session, kind=CrawlKind.QUOTES, trigger=CrawlTrigger.CRON
        )
    assert created2 == []
    assert {j.id for j in existing2} == {j.id for j in created}


@pytest.mark.asyncio
async def test_enqueue_with_codes_snapshot(db):
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(
            session,
            kind=CrawlKind.QUOTES,
            codes_by_type={"STOCK": ["FPT"]},
            portfolio_id=42,
        )
    assert [j.job_type for j in created] == ["stock_quotes"]  # gold: no codes
    assert created[0].params == {
        "codes": ["FPT"],
        "trigger": str(CrawlTrigger.MANUAL),
        "portfolio_id": 42,
    }


@pytest.mark.asyncio
async def test_enqueue_catalog_sync_dedups(db):
    async with db.get_session() as session:
        job, created = await enqueue_catalog_sync(session)
        again, created_again = await enqueue_catalog_sync(session)
    assert created is True and created_again is False
    assert again.id == job.id


# ------------------------------------------------------------------- handlers
def test_all_crawl_job_types_have_handlers():
    for jt in (
        "stock_quotes",
        "gold_quotes",
        "stock_news",
        "stock_ratios",
        "stock_events",
        "stock_ohlcv",
        "catalog_sync",
    ):
        assert jt in SYNC_HANDLERS, f"no handler registered for {jt}"


def test_stock_provider_advertises_ohlcv(storage):
    """OHLCV bypasses ``crawl()`` but must still pass the handler's gate.

    Registration alone never caught this: the handler rejects a kind the
    provider does not advertise, so ``stock_ohlcv`` failed before reaching its
    own branch.
    """
    provider = StockAssetProvider(storage, FakeMarket())
    assert CrawlKind.OHLCV in provider.supported_kinds()


@pytest.mark.asyncio
async def test_dispatched_ohlcv_crawl_succeeds(db, storage, monkeypatch):
    """``stock_ohlcv`` runs end-to-end through the paced-backfill branch."""
    called: dict = {}

    def _fake_backfill(store, codes, *, data_source="VCI", days=7):
        called.update(codes=list(codes), data_source=data_source)
        return len(codes) * 5

    monkeypatch.setattr(
        "kactus_data.jobs.crawl_handlers.crawl_ohlcv_blocking", _fake_backfill
    )

    deps = _deps(db, storage, StockAssetProvider(storage, FakeMarket()))
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(
            session, kind=CrawlKind.OHLCV, codes_by_type={"STOCK": ["FPT", "VCB"]}
        )
    assert [j.job_type for j in created] == ["stock_ohlcv"]

    async with db.get_session() as session:
        view = _view(await SyncJobService.claim_next(session))
    await _run_job(deps, view)

    job = await _get_job(db, created[0].id)
    assert job.status == str(SyncJobStatus.SUCCESS), job.message
    assert job.result == {"total": 2, "rows": 10, "codes": ["FPT", "VCB"]}
    assert called["codes"] == ["FPT", "VCB"]


@pytest.mark.asyncio
async def test_dispatched_crawl_succeeds_and_emits_event(db, storage):
    received = []

    @register_handler(MarketEventName.data_refreshed)
    async def _handler(*, event_name, payload):
        received.append(payload)

    deps = _deps(db, storage, StockAssetProvider(storage, FakeMarket()))
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(
            session,
            kind=CrawlKind.QUOTES,
            codes_by_type={"STOCK": ["FPT", "VCB"]},
        )
    # Mirror the dispatcher: claim (PENDING → RUNNING, stamps started_at), run.
    async with db.get_session() as session:
        claimed = await SyncJobService.claim_next(session)
        view = _view(claimed)
    await _run_job(deps, view)

    job = await _get_job(db, created[0].id)
    assert job.status == str(SyncJobStatus.SUCCESS)
    assert job.result["rows"] == 2
    assert job.progress_done == job.progress_total == 2
    assert job.started_at is not None and job.finished_at is not None

    # SSE nudge emitted with the crawled codes.
    assert received, "expected a data_refreshed event"
    assert received[-1].kind == "quotes"
    assert set(received[-1].codes) == {"FPT", "VCB"}


@pytest.mark.asyncio
async def test_dispatched_crawl_rate_limit_fails_with_full_reason(db, storage):
    """SystemExit mid-crawl → job FAILED with the partial story, process alive."""
    provider = StockAssetProvider(storage, FakeMarket(), RateLimitedMarket())
    deps = _deps(db, storage, provider)
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(
            session,
            kind=CrawlKind.NEWS,
            codes_by_type={"STOCK": ["FPT", "VCB", "ACB"]},
        )
    await _run_job(deps, _view(created[0]))

    job = await _get_job(db, created[0].id)
    assert job.status == str(SyncJobStatus.FAILED)
    assert "rate limit" in job.message
    assert "1/3" in job.message
    assert "1 partial rows" in job.message
    assert (job.progress_done, job.progress_total) == (1, 3)
    # The partial frame was stored before the failure was recorded.
    assert len(provider.read(CrawlKind.NEWS, ["FPT"])) == 1


@pytest.mark.asyncio
async def test_dispatched_crawl_survives_bare_systemexit(db, storage):
    """A SystemExit outside the paced loop still lands as FAILED, not a dead loop."""

    class ExplodingProvider(StockAssetProvider):
        def crawl(self, kind, codes):
            raise SystemExit("Rate limit exceeded")

    deps = _deps(db, storage, ExplodingProvider(storage, FakeMarket()))
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(
            session, kind=CrawlKind.QUOTES, codes_by_type={"STOCK": ["FPT"]}
        )
    await _run_job(deps, _view(created[0]))  # must not raise SystemExit

    job = await _get_job(db, created[0].id)
    assert job.status == str(SyncJobStatus.FAILED)
    assert "vnstock aborted" in job.message


@pytest.mark.asyncio
async def test_handler_resolves_codes_from_watchlist(db, storage):
    """A job enqueued without codes crawls the live watchlist union."""

    class SP:
        async def get_codes_by_type(self):
            return {"STOCK": ["FPT"]}

    deps = _deps(db, storage, StockAssetProvider(storage, FakeMarket()))
    deps.symbol_provider = SP()
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(session, kind=CrawlKind.QUOTES)
    stock_job = next(j for j in created if j.job_type == "stock_quotes")
    await _run_job(deps, _view(stock_job))

    job = await _get_job(db, stock_job.id)
    assert job.status == str(SyncJobStatus.SUCCESS)
    assert job.result["codes"] == ["FPT"]


@pytest.mark.asyncio
async def test_handler_empty_watchlist_is_a_clean_success(db, storage):
    deps = _deps(db, storage, StockAssetProvider(storage, FakeMarket()))
    async with db.get_session() as session:
        created, _ = await enqueue_crawl_jobs(session, kind=CrawlKind.QUOTES)
    stock_job = next(j for j in created if j.job_type == "stock_quotes")
    await _run_job(deps, _view(stock_job))

    job = await _get_job(db, stock_job.id)
    assert job.status == str(SyncJobStatus.SUCCESS)
    assert job.result == {"total": 0, "rows": 0, "codes": []}


# ------------------------------------------------------------------- scheduler
@pytest.mark.asyncio
async def test_scheduled_crawl_enqueues_and_dedups(db):
    """A cron fire enqueues PENDING jobs; a re-fire while live is a no-op."""
    scheduler = build_scheduler(db=db)
    job = next(j for j in scheduler.get_jobs() if j.id == "crawl_quotes")

    await job.func(*job.args)
    await job.func(*job.args)  # second fire lands on live jobs → dedup

    async with db.get_session() as session:
        from sqlalchemy import select

        jobs = list((await session.scalars(select(SyncJob))).all())
    by_type = {j.job_type for j in jobs}
    assert by_type == {"stock_quotes", "gold_quotes"}
    assert len(jobs) == 2, "re-fire must not stack duplicate jobs"
    assert all(j.params["trigger"] == str(CrawlTrigger.CRON) for j in jobs)


def test_crawl_job_type_naming():
    assert crawl_job_type(AssetType.STOCK, CrawlKind.QUOTES) == "stock_quotes"
    assert crawl_job_type(AssetType.GOLD, CrawlKind.QUOTES) == "gold_quotes"
