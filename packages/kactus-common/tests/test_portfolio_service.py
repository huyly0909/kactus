"""Tests for the portfolio domain services.

In-memory SQLite (aiosqlite); exercises the crawl-union query, catalog-validated
item add/remove, catalog upsert/search, and crawl-run dedup.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import ConflictError, NotFoundError
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlStatus, CrawlTrigger
from kactus_common.portfolio.model import SupportedAsset
from kactus_common.portfolio.service import (
    CrawlRunService,
    PortfolioService,
    SupportedAssetService,
)

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


async def _seed_catalog(session, entries: list[tuple[AssetType, str, bool]]):
    for asset_type, code, crawlable in entries:
        session.add(
            SupportedAsset.init(
                asset_type=str(asset_type), code=code, is_crawlable=crawlable
            )
        )
    await session.commit()


@pytest.mark.asyncio
async def test_get_union_codes_dedups_and_groups(db):
    """Union is DISTINCT, grouped by asset_type, across multiple owners."""
    async with db.get_session() as session:
        await _seed_catalog(
            session,
            [
                (AssetType.STOCK, "FPT", True),
                (AssetType.STOCK, "VCB", True),
                (AssetType.GOLD, "SJC", True),
            ],
        )
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        p2 = await PortfolioService.create(session, name="B", owner_id=2)
        # FPT appears in both portfolios → must dedup to one entry.
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
        )
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.GOLD, code="SJC"
        )
        await PortfolioService.add_item(
            session, portfolio_id=p2.id, asset_type=AssetType.STOCK, code="FPT"
        )
        await PortfolioService.add_item(
            session, portfolio_id=p2.id, asset_type=AssetType.STOCK, code="VCB"
        )

        union = await PortfolioService.get_union_codes_by_type(session)

    assert sorted(union[AssetType.STOCK]) == ["FPT", "VCB"]
    assert union[AssetType.GOLD] == ["SJC"]


@pytest.mark.asyncio
async def test_union_excludes_non_crawlable_and_deleted(db):
    """Non-crawlable catalog rows and items of deleted portfolios are excluded."""
    async with db.get_session() as session:
        await _seed_catalog(
            session,
            [
                (AssetType.STOCK, "FPT", True),
                (AssetType.STOCK, "DEAD", False),  # not crawlable
            ],
        )
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        p2 = await PortfolioService.create(session, name="B", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
        )
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="DEAD"
        )
        await PortfolioService.add_item(
            session, portfolio_id=p2.id, asset_type=AssetType.STOCK, code="FPT"
        )
        # Soft-delete p2 — its FPT membership should not affect the union here,
        # but p1 still keeps FPT alive.
        await PortfolioService.delete(session, p2)

        union = await PortfolioService.get_union_codes_by_type(session)

    assert union.get(AssetType.STOCK) == ["FPT"]  # DEAD excluded


@pytest.mark.asyncio
async def test_deleting_only_portfolio_empties_union(db):
    async with db.get_session() as session:
        await _seed_catalog(session, [(AssetType.STOCK, "FPT", True)])
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
        )
        await PortfolioService.delete(session, p1)
        union = await PortfolioService.get_union_codes_by_type(session)
    assert union == {}


@pytest.mark.asyncio
async def test_add_item_rejects_uncatalogued_code(db):
    async with db.get_session() as session:
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        with pytest.raises(NotFoundError):
            await PortfolioService.add_item(
                session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="NOPE"
            )


@pytest.mark.asyncio
async def test_add_item_duplicate_conflicts(db):
    async with db.get_session() as session:
        await _seed_catalog(session, [(AssetType.STOCK, "FPT", True)])
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="fpt"
        )
        with pytest.raises(ConflictError):
            await PortfolioService.add_item(
                session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
            )


@pytest.mark.asyncio
async def test_remove_item(db):
    async with db.get_session() as session:
        await _seed_catalog(session, [(AssetType.STOCK, "FPT", True)])
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
        )
        await PortfolioService.remove_item(
            session, portfolio_id=p1.id, asset_type=AssetType.STOCK, code="FPT"
        )
        items = await PortfolioService.get_items(session, p1.id)
    assert items == []


@pytest.mark.asyncio
async def test_get_owned_or_404_hides_other_owners(db):
    async with db.get_session() as session:
        p1 = await PortfolioService.create(session, name="A", owner_id=1)
        # Owner 2 cannot see owner 1's portfolio.
        with pytest.raises(NotFoundError):
            await PortfolioService.get_owned_or_404(
                session, portfolio_id=p1.id, owner_id=2
            )
        # Owner 1 can.
        got = await PortfolioService.get_owned_or_404(
            session, portfolio_id=p1.id, owner_id=1
        )
    assert got.id == p1.id


@pytest.mark.asyncio
async def test_catalog_upsert_and_search_by_tag(db):
    async with db.get_session() as session:
        n = await SupportedAssetService.upsert_many(
            session,
            asset_type=AssetType.STOCK,
            entries=[
                {"code": "FPT", "name": "FPT Corp", "tags": ["VN30", "VN100"]},
                {"code": "SSI", "name": "SSI", "tags": ["VN100"]},
            ],
        )
        assert n == 2
        # Idempotent upsert updates rather than duplicates.
        await SupportedAssetService.upsert_many(
            session,
            asset_type=AssetType.STOCK,
            entries=[{"code": "FPT", "name": "FPT Corporation", "tags": ["VN30"]}],
        )
        vn30 = await SupportedAssetService.search(
            session, asset_type=AssetType.STOCK, tag="VN30"
        )
        codes = {a.code for a in vn30}
    assert codes == {"FPT"}  # SSI is VN100-only


@pytest.mark.asyncio
async def test_crawl_run_lifecycle_and_dedup(db):
    async with db.get_session() as session:
        run = await CrawlRunService.start(
            session,
            asset_type=AssetType.STOCK,
            kind=CrawlKind.QUOTES,
            trigger=CrawlTrigger.MANUAL,
        )
        # An in-flight run blocks a duplicate manual refresh.
        assert await CrawlRunService.has_inflight(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )
        await CrawlRunService.finish(
            session, run, rows_written=5, status=CrawlStatus.SUCCESS
        )
        # Once finished, no longer in-flight.
        assert not await CrawlRunService.has_inflight(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )
        recent = await CrawlRunService.list_recent(session)
    assert recent[0].rows_written == 5
    assert recent[0].status == str(CrawlStatus.SUCCESS)
