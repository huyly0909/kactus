"""CLI commands for financial data collection.

Usage::

    python manage.py data finance -s VCI --report-type income_statement --period quarter
"""

from datetime import date

import typer
from typer import Context, Option, Typer

cli = Typer()


@cli.callback(invoke_without_command=True)
def main(
    ctx: Context,
    symbol: str = Option(..., "--symbol", "-s", help="Stock symbol (e.g. VCI, ACB)"),
    report_type: str = Option(
        "income_statement",
        "--report-type",
        "-r",
        help="Report type: income_statement, balance_sheet, cash_flow, ratio",
    ),
    period: str = Option("quarter", "--period", "-p", help="Period: quarter or year"),
    db_path: str = Option("kactus.duckdb", help="Path to DuckDB database file"),
    data_source: str = Option("KBS", "--data-source", "-d", help="Data source: KBS or VCI"),
):
    """Sync financial reports for a stock symbol."""
    from kactus_data.pipeline import SyncPipeline
    from kactus_data.storage.duckdb import DuckDBStorage
    from kactus_data.sources.finance.vnstock import VnstockFinanceSource
    from kactus_data.sources.finance.tables import FINANCE_TABLE

    today = date.today()

    typer.echo(f"Syncing {report_type}: {symbol} period={period} source={data_source}")

    source = VnstockFinanceSource(source=data_source, report_type=report_type, period=period)
    storage = DuckDBStorage(db_path)
    pipeline = SyncPipeline(source, storage)

    result = pipeline.run(
        table=FINANCE_TABLE,
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
