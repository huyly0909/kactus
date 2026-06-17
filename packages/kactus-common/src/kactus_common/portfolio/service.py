"""Portfolio services — DB operations for portfolios, catalog, and crawl runs.

Stateless static methods, mirroring :class:`kactus_common.project.service`.
The cross-package seam is :meth:`PortfolioService.get_union_codes_by_type`,
consumed (indirectly, via a ``SymbolProvider``) by ``kactus-data`` crawl jobs.
"""

from __future__ import annotations

import datetime
import time

from kactus_common.database.oltp.models import utcnow
from kactus_common.exceptions import ConflictError, NotFoundError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .const import AssetType, CrawlKind, CrawlStatus, CrawlTrigger
from .model import CrawlRun, Portfolio, PortfolioItem, SupportedAsset


class PortfolioService:
    """CRUD for portfolios + the crawl-union query."""

    # ------------------------------------------------------------------ CRUD
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        name: str,
        owner_id: int,
        description: str | None = None,
    ) -> Portfolio:
        """Create a portfolio owned by ``owner_id``."""
        portfolio = Portfolio.init(
            name=name,
            description=description,
            owner_id=owner_id,
            created_by=owner_id,
        )
        session.add(portfolio)
        await session.commit()
        await session.refresh(portfolio)
        return portfolio

    @staticmethod
    async def get_or_404(session: AsyncSession, portfolio_id: int) -> Portfolio:
        """Fetch a portfolio by id or raise ``NotFoundError``."""
        return await Portfolio.get_or_404(session, portfolio_id)

    @staticmethod
    async def get_owned_or_404(
        session: AsyncSession, *, portfolio_id: int, owner_id: int
    ) -> Portfolio:
        """Fetch a portfolio and assert ``owner_id`` owns it.

        Raises ``NotFoundError`` if missing or owned by someone else — we do not
        leak existence of other users' portfolios.
        """
        portfolio = await Portfolio.get(session, portfolio_id)
        if portfolio is None or portfolio.owner_id != owner_id:
            raise NotFoundError(f"Portfolio record, pk: {portfolio_id}")
        return portfolio

    @staticmethod
    async def list_for_owner(
        session: AsyncSession, owner_id: int
    ) -> list[Portfolio]:
        """All non-deleted portfolios owned by ``owner_id``."""
        return await Portfolio.all(session, owner_id=owner_id)

    @staticmethod
    async def list_all(session: AsyncSession) -> list[Portfolio]:
        """All non-deleted portfolios (admin)."""
        return await Portfolio.all(session)

    @staticmethod
    async def update(
        session: AsyncSession,
        portfolio: Portfolio,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Portfolio:
        """Update mutable portfolio fields."""
        if name is not None:
            portfolio.name = name
        if description is not None:
            portfolio.description = description
        await portfolio.save(session)
        return portfolio

    @staticmethod
    async def delete(session: AsyncSession, portfolio: Portfolio) -> None:
        """Logically delete a portfolio (items are left orphaned but unread)."""
        portfolio.deleted_timestamp = int(time.time())
        await portfolio.save(session)

    # ------------------------------------------------------------------ items
    @staticmethod
    async def get_items(
        session: AsyncSession, portfolio_id: int
    ) -> list[PortfolioItem]:
        """All items in a portfolio."""
        return await PortfolioItem.all(session, portfolio_id=portfolio_id)

    @staticmethod
    async def add_item(
        session: AsyncSession,
        *,
        portfolio_id: int,
        asset_type: AssetType,
        code: str,
    ) -> PortfolioItem:
        """Add an instrument to a portfolio, validated against the catalog."""
        code = code.strip().upper()
        asset = await SupportedAsset.first(
            session, asset_type=str(asset_type), code=code
        )
        if asset is None:
            raise NotFoundError(
                f"Asset {asset_type}:{code} is not in the supported catalog"
            )

        existing = await PortfolioItem.first(
            session, portfolio_id=portfolio_id, asset_type=str(asset_type), code=code
        )
        if existing:
            raise ConflictError(
                f"{asset_type}:{code} is already in this portfolio",
                data={"asset_type": str(asset_type), "code": code},
            )

        item = PortfolioItem.init(
            portfolio_id=portfolio_id, asset_type=str(asset_type), code=code
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item

    @staticmethod
    async def remove_item(
        session: AsyncSession,
        *,
        portfolio_id: int,
        asset_type: AssetType,
        code: str,
    ) -> None:
        """Remove an instrument from a portfolio."""
        item = await PortfolioItem.first(
            session,
            portfolio_id=portfolio_id,
            asset_type=str(asset_type),
            code=code.strip().upper(),
        )
        if not item:
            raise NotFoundError(f"{asset_type}:{code} not found in this portfolio")
        await item.delete(session)

    # --------------------------------------------------------------- crawl union
    @staticmethod
    async def get_union_codes_by_type(
        session: AsyncSession,
    ) -> dict[AssetType, list[str]]:
        """DISTINCT crawlable codes across all live portfolios, grouped by type.

        The join on :class:`Portfolio` lets the soft-delete filter drop items of
        deleted portfolios; the join on :class:`SupportedAsset` restricts to
        ``is_crawlable`` instruments.  This is the single source of "what to
        crawl" — the cron and manual-refresh paths both call it.
        """
        stmt = (
            select(PortfolioItem.asset_type, PortfolioItem.code)
            .join(Portfolio, Portfolio.id == PortfolioItem.portfolio_id)
            .join(
                SupportedAsset,
                and_(
                    SupportedAsset.asset_type == PortfolioItem.asset_type,
                    SupportedAsset.code == PortfolioItem.code,
                ),
            )
            .where(SupportedAsset.is_crawlable.is_(True))
            .distinct()
        )
        rows = (await session.execute(stmt)).all()
        result: dict[AssetType, list[str]] = {}
        for asset_type, code in rows:
            result.setdefault(AssetType(asset_type), []).append(code)
        return result


class SupportedAssetService:
    """Catalog management — search + sync upsert."""

    @staticmethod
    async def get(
        session: AsyncSession, *, asset_type: AssetType, code: str
    ) -> SupportedAsset | None:
        return await SupportedAsset.first(
            session, asset_type=str(asset_type), code=code.strip().upper()
        )

    @staticmethod
    async def search(
        session: AsyncSession,
        *,
        asset_type: AssetType | None = None,
        q: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[SupportedAsset]:
        """Search the catalog for the asset-picker.

        ``tag`` (e.g. ``VN30``) is filtered in Python — the catalog is small
        (~a few thousand rows) and JSON ``contains`` is not portable across
        Postgres/SQLite.
        """
        stmt = select(SupportedAsset)
        if asset_type is not None:
            stmt = stmt.where(SupportedAsset.asset_type == str(asset_type))
        if q:
            like = f"%{q.strip().upper()}%"
            stmt = stmt.where(SupportedAsset.code.ilike(like))
        stmt = stmt.limit(limit if not tag else 1000)
        rows = list((await session.scalars(stmt)).all())
        if tag:
            rows = [r for r in rows if r.tags and tag in r.tags][:limit]
        return rows

    @staticmethod
    async def upsert_many(
        session: AsyncSession,
        *,
        asset_type: AssetType,
        entries: list[dict],
    ) -> int:
        """Upsert catalog entries from a sync. ``entries`` items: ``{code, name,
        tags, meta_json}``. Returns the number of rows written."""
        now = utcnow()
        existing = {
            a.code: a
            for a in await SupportedAsset.all(session, asset_type=str(asset_type))
        }
        written = 0
        for entry in entries:
            code = str(entry["code"]).strip().upper()
            row = existing.get(code)
            if row is None:
                row = SupportedAsset.init(
                    asset_type=str(asset_type),
                    code=code,
                    name=entry.get("name"),
                    is_crawlable=entry.get("is_crawlable", True),
                    tags=entry.get("tags") or [],
                    meta_json=entry.get("meta_json") or {},
                    synced_at=now,
                )
                session.add(row)
            else:
                row.name = entry.get("name", row.name)
                if "tags" in entry:
                    row.tags = entry["tags"] or []
                if "meta_json" in entry:
                    row.meta_json = entry["meta_json"] or {}
                row.synced_at = now
            written += 1
        await session.commit()
        return written


class CrawlRunService:
    """Lifecycle + dedup for crawl-run audit records."""

    @staticmethod
    async def start(
        session: AsyncSession,
        *,
        asset_type: AssetType,
        kind: CrawlKind,
        trigger: CrawlTrigger = CrawlTrigger.CRON,
        portfolio_id: int | None = None,
    ) -> CrawlRun:
        run = CrawlRun.init(
            asset_type=str(asset_type),
            kind=str(kind),
            trigger=str(trigger),
            portfolio_id=portfolio_id,
            status=str(CrawlStatus.RUNNING),
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run

    @staticmethod
    async def finish(
        session: AsyncSession,
        run: CrawlRun,
        *,
        rows_written: int = 0,
        status: CrawlStatus = CrawlStatus.SUCCESS,
        error: str | None = None,
    ) -> CrawlRun:
        run.status = str(status)
        run.rows_written = rows_written
        run.error = error
        run.finished_at = utcnow()
        await run.save(session)
        return run

    @staticmethod
    async def has_inflight(
        session: AsyncSession,
        *,
        asset_type: AssetType,
        kind: CrawlKind,
        within_minutes: int = 15,
    ) -> bool:
        """True if a same-(type, kind) run is RUNNING and recent.

        Powers manual-refresh dedup so a user mashing the refresh button cannot
        stack duplicate crawls.  The recency window prevents a crashed run stuck
        in RUNNING from blocking forever.
        """
        cutoff = utcnow() - datetime.timedelta(minutes=within_minutes)
        stmt = (
            select(CrawlRun.id)
            .where(
                CrawlRun.asset_type == str(asset_type),
                CrawlRun.kind == str(kind),
                CrawlRun.status == str(CrawlStatus.RUNNING),
                CrawlRun.create_time >= cutoff,
            )
            .limit(1)
        )
        return (await session.scalars(stmt)).first() is not None

    @staticmethod
    async def list_recent(
        session: AsyncSession, *, limit: int = 50
    ) -> list[CrawlRun]:
        stmt = select(CrawlRun).order_by(CrawlRun.create_time.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())
