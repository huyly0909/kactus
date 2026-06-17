"""kactus-fin implementation of the ``SymbolProvider`` seam.

Computes the crawl universe = (union of all users' watchlists) ∪ (VN30/VN100
baseline).  Injected into kactus-data crawl jobs so the data layer never imports
kactus-fin and stays portfolio-ignorant.
"""

from __future__ import annotations

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.service import PortfolioService, SupportedAssetService


class FinSymbolProvider:
    """Live crawl-code provider backed by the OLTP database."""

    def __init__(
        self,
        db: DatabaseSessionManager,
        *,
        baseline_tags: tuple[str, ...] = ("VN30", "VN100"),
    ) -> None:
        self.db = db
        self.baseline_tags = baseline_tags

    async def get_codes_by_type(self) -> dict[str, list[str]]:
        async with self.db.get_session() as session:
            union = await PortfolioService.get_union_codes_by_type(session)
            result: dict[str, set[str]] = {
                str(at): set(codes) for at, codes in union.items()
            }

            # Always crawl the index baseline (VN30/VN100), even if no user
            # currently watches those names.
            baseline: set[str] = set()
            for tag in self.baseline_tags:
                assets = await SupportedAssetService.search(
                    session, asset_type=AssetType.STOCK, tag=tag, limit=1000
                )
                baseline.update(a.code for a in assets)
            if baseline:
                result.setdefault(str(AssetType.STOCK), set()).update(baseline)

        return {at: sorted(codes) for at, codes in result.items() if codes}
