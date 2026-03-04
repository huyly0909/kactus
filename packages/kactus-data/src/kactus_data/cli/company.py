"""CLI commands for company data collection.

Usage::

    python manage.py data company -s VCI
"""

from datetime import date

import typer
from typer import Context, Option, Typer

from kactus_data.config import DataSettings

cli = Typer()

_defaults = DataSettings()


@cli.callback(invoke_without_command=True)
def main(
    ctx: Context,
    symbol: str = Option(..., "--symbol", "-s", help="Stock symbol (e.g. VCI, ACB)"),
    db_path: str = Option(_defaults.db_path, help="Path to DuckDB database file"),
    data_source: str = Option("VCI", "--data-source", "-d", help="Data source: KBS or VCI"),
):
    """Sync company overview for a stock symbol."""
    from kactus_data.pipeline import SyncPipeline
    from kactus_data.storage.duckdb import DuckDBStorage
    from kactus_data.sources.company.vnstock import VnstockCompanySource
    from kactus_data.sources.company.tables import COMPANY_TABLE

    today = date.today()

    typer.echo(f"Syncing company overview: {symbol} source={data_source}")

    source = VnstockCompanySource(source=data_source)
    storage = DuckDBStorage(db_path)
    pipeline = SyncPipeline(source, storage)

    result = pipeline.run(
        table=COMPANY_TABLE,
        code=symbol,
        start_date=today,
        end_date=today,
    )

    if result.success:
        typer.secho(
            f"✓ Fetched {result.rows_fetched} rows, stored {result.rows_stored} in {result.duration_ms:.0f}ms",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f"✗ Failed: {result.error}", fg=typer.colors.RED)
        raise typer.Exit(1)
