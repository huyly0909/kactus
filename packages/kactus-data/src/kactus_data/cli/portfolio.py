"""Portfolio crawl & catalog CLI (ops / manual triggers).

Examples::

    python manage.py data portfolio sync-catalog --asset-type stock
    python manage.py data portfolio crawl --kind quotes --codes FPT,VCB
"""

from __future__ import annotations

import asyncio

import typer
from kactus_common.cli import AsyncTyper
from kactus_common.database.oltp.session import get_db
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_data.config import get_settings
from kactus_data.jobs.crawl import run_crawl, sync_catalog
from kactus_data.portfolio.provider import build_providers
from kactus_data.sources.stock.auth import init_vnstock_auth
from kactus_data.storage.duckdb import DuckDBStorage

cli = AsyncTyper(help="Portfolio crawl & catalog operations")


def _bootstrap():
    """Register settings, authenticate vnstock, build storage + providers."""
    settings = get_settings()
    init_vnstock_auth()
    storage = DuckDBStorage(settings.db_path)
    providers = build_providers(
        storage,
        data_source=settings.data_source,
        mihong_token=getattr(settings, "mihong_xsrf_token", ""),
    )
    return get_db(), providers


@cli.command("sync-catalog")
def sync_catalog_cmd(
    asset_type: str = typer.Option("stock", "--asset-type", "-a", help="stock | gold"),
):
    """Refresh the supported-asset catalog for an asset type."""
    db, providers = _bootstrap()
    at = AssetType(asset_type.upper())
    out = asyncio.run(sync_catalog(db=db, providers=providers, asset_types=[at]))
    typer.secho(f"✓ Catalog synced: {out}", fg=typer.colors.GREEN)


@cli.command()
def crawl(
    kind: str = typer.Option("quotes", "--kind", "-k", help="quotes|news|foreign_trade|ratios|events"),
    codes: str = typer.Option(..., "--codes", "-c", help="Comma-separated codes, e.g. FPT,VCB"),
    asset_type: str = typer.Option("stock", "--asset-type", "-a", help="stock | gold"),
):
    """Crawl a dataset for an explicit set of codes (bypasses the watchlist union)."""
    db, providers = _bootstrap()
    code_list = [c.strip().upper() for c in codes.split(",") if c.strip()]
    if not code_list:
        typer.secho("No codes given", fg=typer.colors.RED)
        raise typer.Exit(1)
    run_ids = asyncio.run(
        run_crawl(
            db=db,
            providers=providers,
            kind=CrawlKind(kind),
            codes_by_type={asset_type.upper(): code_list},
            trigger=CrawlTrigger.MANUAL,
        )
    )
    typer.secho(f"✓ Crawl runs: {run_ids}", fg=typer.colors.GREEN)
