"""CLI commands for stock price data collection.

Usage::

    python manage.py data stock ohlcv -s VCI --start 2024-01-01 --end 2024-12-31
    python manage.py data stock listing
"""

from datetime import date

import typer
from typer import Context, Option, Typer

from kactus_data.config import DataSettings

cli = Typer()

_defaults = DataSettings()


@cli.callback()
def main(
    ctx: Context,
    db_path: str = Option(_defaults.db_path, help="Path to DuckDB database file"),
    data_source: str = Option(_defaults.data_source, "--data-source", "-d", help="Data source: KBS or VCI"),
):
    """Stock price data collection commands."""
    from kactus_data.storage.duckdb import DuckDBStorage

    ctx.obj = {"storage": DuckDBStorage(db_path), "data_source": data_source}



@cli.command()
def ohlcv(
    ctx: Context,
    symbol: str = Option(..., "--symbol", "-s", help="Stock symbol (e.g. VCI, ACB)"),
    start: str = Option(..., "--start", help="Start date (YYYY-MM-DD)"),
    end: str = Option(..., "--end", help="End date (YYYY-MM-DD)"),
    interval: str = Option("1D", "--interval", "-i", help="Interval: 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M"),
):
    """Sync OHLCV (candlestick) data for a stock symbol."""
    from kactus_data.pipeline import SyncPipeline
    from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
    from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    source_name = ctx.obj["data_source"]

    typer.echo(f"Syncing OHLCV: {symbol} [{start} → {end}] interval={interval} source={source_name}")

    source = VnstockOHLCVSource(source=source_name, interval=interval)
    storage = ctx.obj["storage"]
    pipeline = SyncPipeline(source, storage)

    result = pipeline.run(
        table=STOCK_OHLCV_TABLE,
        code=symbol,
        start_date=start_date,
        end_date=end_date,
    )

    if result.success:
        typer.secho(
            f"✓ Fetched {result.rows_fetched} rows, stored {result.rows_stored} in {result.duration_ms:.0f}ms",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"✗ Failed: {result.error}", fg=typer.colors.RED)
        raise typer.Exit(1)


@cli.command()
def listing(ctx: Context):
    """Sync all listed stock symbols."""
    from kactus_data.pipeline import SyncPipeline
    from kactus_data.sources.stock.vnstock import VnstockListingSource
    from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE

    source_name = ctx.obj["data_source"]
    today = date.today()

    typer.echo(f"Syncing all stock listings from {source_name} ...")

    source = VnstockListingSource(source=source_name)
    storage = ctx.obj["storage"]
    pipeline = SyncPipeline(source, storage)

    result = pipeline.run(
        table=STOCK_LISTING_TABLE,
        code="ALL",
        start_date=today,
        end_date=today,
    )

    if result.success:
        typer.secho(
            f"✓ Fetched {result.rows_fetched} symbols, stored {result.rows_stored} in {result.duration_ms:.0f}ms",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"✗ Failed: {result.error}", fg=typer.colors.RED)
        raise typer.Exit(1)
