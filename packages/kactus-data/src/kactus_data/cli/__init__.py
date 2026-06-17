"""kactus-data CLI — ETL management commands."""

from kactus_common.cli import AsyncTyper

cli = AsyncTyper(help="Kactus Data — ETL pipelines & backups")


def _add_subcommands():
    from kactus_data.cli import backup, sync, stock, company, finance, portfolio  # noqa: F401

    cli.add_typer(backup.cli, name="backup", help="DuckDB backup / export")
    cli.add_typer(stock.cli, name="stock", help="Stock price data (OHLCV, listings)")
    cli.add_typer(company.cli, name="company", help="Company overview data")
    cli.add_typer(finance.cli, name="finance", help="Financial statements & ratios")
    cli.add_typer(portfolio.cli, name="portfolio", help="Portfolio crawl & catalog ops")


_add_subcommands()

